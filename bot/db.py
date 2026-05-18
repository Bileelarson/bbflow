"""SQLite DB layer for Klein public bot.

Schema:
  users         — user records (free/premium plan, expiry, gen counts)
  generations   — every gen attempt logged
  payments      — payment requests with unique codes
"""
import json
import secrets
import sqlite3
import string
import time
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH, ADMIN_IDS as ADMIN_USER_IDS  # noqa: F401

# Plan constants
PLAN_FREE     = "free"
PLAN_WEEKLY   = "weekly"
PLAN_MONTHLY  = "monthly"

PLAN_DURATION_DAYS = {
    PLAN_WEEKLY:  7,
    PLAN_MONTHLY: 30,
}

PLAN_PRICE_IDR = {
    PLAN_WEEKLY:  50_000,
    PLAN_MONTHLY: 150_000,
}


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


def init_db():
    """Create tables if not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                first_name     TEXT,
                plan           TEXT NOT NULL DEFAULT 'free',
                expires_at     INTEGER,            -- unix ts when premium ends (NULL = never)
                free_used      INTEGER DEFAULT 0,  -- count of free trials used (max 3)
                gen_count      INTEGER DEFAULT 0,  -- lifetime gen count
                last_gen_at    INTEGER DEFAULT 0,  -- rate limit anchor
                captcha_passed INTEGER DEFAULT 0,
                created_at     INTEGER NOT NULL,
                updated_at     INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS generations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                kind        TEXT NOT NULL,         -- 'image' or 'video'
                prompt      TEXT,
                gen_id      TEXT,                  -- Leonardo gen UUID
                status      TEXT,                  -- 'success' / 'failed'
                error       TEXT,
                created_at  INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                code            TEXT PRIMARY KEY,  -- e.g. IMAJIN-A1B2-C3D4
                user_id         INTEGER NOT NULL,
                plan            TEXT NOT NULL,     -- 'weekly' / 'monthly'
                amount          INTEGER NOT NULL,  -- IDR
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected
                screenshot_id   TEXT,              -- Telegram file_id of user's payment screenshot
                rejected_reason TEXT,
                requested_at    INTEGER NOT NULL,
                paid_at         INTEGER,
                approved_at     INTEGER,
                approved_by     INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id  INTEGER NOT NULL,    -- user yang invite
                invited_id   INTEGER NOT NULL,    -- user yang join via link
                bonus_given  INTEGER DEFAULT 0,   -- 0 = pending, 1 = bonus diberikan setelah captcha
                created_at   INTEGER NOT NULL,
                UNIQUE(invited_id),               -- 1 user cuma bisa jadi referee 1x
                FOREIGN KEY(referrer_id) REFERENCES users(user_id),
                FOREIGN KEY(invited_id)  REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_generations_user ON generations(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, status);
            CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status, requested_at);
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
        """)

        # Add bonus_trials column if not exists (migration safe)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            if "bonus_trials" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN bonus_trials INTEGER DEFAULT 0")
            if "lang" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'id'")
        except Exception:
            pass


def get_lang(user_id: int) -> str:
    """Return user language code ('id' or 'en'). Default 'id'."""
    with conn() as c:
        row = c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row or not row["lang"]:
        return "id"
    return row["lang"] if row["lang"] in ("id", "en") else "id"


def set_lang(user_id: int, lang: str) -> None:
    """Set user language. Only 'id' or 'en' accepted."""
    if lang not in ("id", "en"):
        lang = "id"
    now = int(time.time())
    with conn() as c:
        c.execute(
            "UPDATE users SET lang = ?, updated_at = ? WHERE user_id = ?",
            (lang, now, user_id),
        )


def upsert_user(user_id: int, username: str | None = None, first_name: str | None = None) -> dict:
    """Insert or update user, return current user record."""
    now = int(time.time())
    with conn() as c:
        c.execute("""
            INSERT INTO users (user_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                updated_at = excluded.updated_at
        """, (user_id, username, first_name, now, now))
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {}


def get_user(user_id: int) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def is_premium(user_id: int) -> bool:
    """Active premium check (plan != free AND expires_at > now)."""
    if is_admin(user_id):
        return True
    u = get_user(user_id)
    if not u or u["plan"] == PLAN_FREE:
        return False
    if not u["expires_at"]:
        return False
    return u["expires_at"] > int(time.time())


FREE_TRIAL_LIMIT = 2  # 2x image gen lifetime per user (referral bonus tersedia)
REFERRAL_BONUS_REFERRER = 1  # bonus ke yang invite
REFERRAL_BONUS_INVITED  = 1  # bonus ke yang diinvite


def free_trial_remaining(user_id: int) -> int:
    """Sisa free trial = (FREE_TRIAL_LIMIT + bonus_trials) - free_used. Min 0."""
    if is_admin(user_id) or is_premium(user_id):
        return 999  # unlimited
    user = get_user(user_id)
    if not user:
        return FREE_TRIAL_LIMIT
    used = user.get("free_used", 0) or 0
    bonus = user.get("bonus_trials", 0) or 0
    remaining = (FREE_TRIAL_LIMIT + bonus) - used
    return max(0, remaining)


def add_bonus_trials(user_id: int, amount: int) -> int:
    """Add bonus trials to user. Returns new total bonus_trials."""
    now = int(time.time())
    with conn() as c:
        c.execute("""
            UPDATE users SET bonus_trials = COALESCE(bonus_trials, 0) + ?, updated_at = ?
            WHERE user_id = ?
        """, (amount, now, user_id))
        row = c.execute("SELECT bonus_trials FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else 0


def record_referral(referrer_id: int, invited_id: int) -> bool:
    """Record a new referral. Returns True if new (False if already exists or self-ref).

    Bonus_given = 0 (akan di-grant saat invited user pass captcha).
    """
    if referrer_id == invited_id:
        return False
    if is_admin(invited_id):
        return False  # admin tidak boleh jadi referee
    now = int(time.time())
    try:
        with conn() as c:
            c.execute("""
                INSERT INTO referrals (referrer_id, invited_id, bonus_given, created_at)
                VALUES (?, ?, 0, ?)
            """, (referrer_id, invited_id, now))
        return True
    except Exception:
        # UNIQUE constraint — invited_id sudah pernah ke-record
        return False


def grant_referral_bonus(invited_id: int) -> tuple[int, int] | None:
    """Grant bonus to both referrer and invited user. Idempotent (only grants once).

    Returns (referrer_id, referrer_bonus_count) on success, or None if no referral / already granted.
    """
    with conn() as c:
        row = c.execute("""
            SELECT referrer_id FROM referrals
            WHERE invited_id = ? AND bonus_given = 0
        """, (invited_id,)).fetchone()
        if not row:
            return None
        referrer_id = row[0]
        # Mark granted
        c.execute("UPDATE referrals SET bonus_given = 1 WHERE invited_id = ?", (invited_id,))
    # Add bonuses
    add_bonus_trials(referrer_id, REFERRAL_BONUS_REFERRER)
    add_bonus_trials(invited_id, REFERRAL_BONUS_INVITED)
    # Return referrer info for notif
    with conn() as c:
        cnt = c.execute("""
            SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_given = 1
        """, (referrer_id,)).fetchone()[0]
    return (referrer_id, cnt)


def referral_stats(user_id: int) -> dict:
    """Get referral stats for a user."""
    with conn() as c:
        total = c.execute("""
            SELECT COUNT(*) FROM referrals WHERE referrer_id = ?
        """, (user_id,)).fetchone()[0]
        granted = c.execute("""
            SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_given = 1
        """, (user_id,)).fetchone()[0]
        pending = total - granted
    return {"total": total, "granted": granted, "pending": pending}

def can_use_free_trial(user_id: int) -> tuple[bool, str]:
    """Check if user can do free trial (3x image lifetime).
    Returns (allowed, reason_if_not).
    """
    if is_admin(user_id):
        return True, ""
    if is_premium(user_id):
        return True, ""
    u = get_user(user_id)
    if not u:
        return True, ""
    used = u["free_used"] or 0
    if used >= FREE_TRIAL_LIMIT:
        return False, "trial_exhausted"
    return True, ""


def mark_free_used(user_id: int):
    """Increment free trial counter (was: set to 1)."""
    with conn() as c:
        c.execute(
            "UPDATE users SET free_used = COALESCE(free_used, 0) + 1, "
            "updated_at=? WHERE user_id=?",
            (int(time.time()), user_id),
        )


def mark_captcha_passed(user_id: int):
    with conn() as c:
        c.execute(
            "UPDATE users SET captcha_passed=1, updated_at=? WHERE user_id=?",
            (int(time.time()), user_id),
        )


def captcha_passed(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    u = get_user(user_id)
    return bool(u and u["captcha_passed"])


def check_rate_limit(user_id: int, cooldown_seconds: int = 30) -> tuple[bool, int]:
    """Return (allowed, seconds_remaining_if_blocked)."""
    if is_admin(user_id):
        return True, 0
    u = get_user(user_id)
    if not u:
        return True, 0
    elapsed = int(time.time()) - (u["last_gen_at"] or 0)
    if elapsed < cooldown_seconds:
        return False, cooldown_seconds - elapsed
    return True, 0


def record_generation(user_id: int, kind: str, prompt: str, gen_id: str | None,
                      status: str, error: str | None = None):
    now = int(time.time())
    with conn() as c:
        c.execute("""
            INSERT INTO generations (user_id, kind, prompt, gen_id, status, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, kind, prompt[:500] if prompt else None, gen_id, status, error, now))
        c.execute("""
            UPDATE users SET gen_count = gen_count + 1, last_gen_at = ?, updated_at = ?
            WHERE user_id = ?
        """, (now, now, user_id))


def _gen_code() -> str:
    """IMAJIN-XXXX-YYYY format (uppercase alnum, no confusing chars)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
    a = "".join(secrets.choice(alphabet) for _ in range(4))
    b = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"IMAJIN-{a}-{b}"


def create_payment_request(user_id: int, plan: str) -> dict:
    """Generate unique payment code for user. Returns the row."""
    if plan not in PLAN_DURATION_DAYS:
        raise ValueError(f"invalid plan: {plan}")
    amount = PLAN_PRICE_IDR[plan]
    now = int(time.time())
    # Try 5x to get unique code
    for _ in range(5):
        code = _gen_code()
        try:
            with conn() as c:
                c.execute("""
                    INSERT INTO payments (code, user_id, plan, amount, status, requested_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                """, (code, user_id, plan, amount, now))
            return get_payment(code)
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("failed to generate unique code")


def get_payment(code: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM payments WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def get_pending_payment_for_user(user_id: int) -> dict | None:
    """Latest pending payment for this user."""
    with conn() as c:
        row = c.execute("""
            SELECT * FROM payments
            WHERE user_id = ? AND status = 'pending'
            ORDER BY requested_at DESC LIMIT 1
        """, (user_id,)).fetchone()
        return dict(row) if row else None


def attach_screenshot(code: str, screenshot_file_id: str) -> bool:
    now = int(time.time())
    with conn() as c:
        cur = c.execute("""
            UPDATE payments SET screenshot_id=?, paid_at=?
            WHERE code=? AND status='pending'
        """, (screenshot_file_id, now, code))
        return cur.rowcount > 0


def list_pending_payments(limit: int = 20) -> list[dict]:
    with conn() as c:
        rows = c.execute("""
            SELECT p.*, u.username, u.first_name
            FROM payments p
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE p.status = 'pending' AND p.screenshot_id IS NOT NULL
            ORDER BY p.requested_at ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def approve_payment(code: str, admin_id: int) -> dict | None:
    """Mark payment approved + activate user's premium plan. Returns user row."""
    p = get_payment(code)
    if not p or p["status"] != "pending":
        return None
    now = int(time.time())
    duration = PLAN_DURATION_DAYS[p["plan"]] * 86400

    # Stack on existing premium (if user already premium and not expired)
    u = get_user(p["user_id"])
    base = max(now, u["expires_at"] or 0) if u else now
    new_expires = base + duration

    with conn() as c:
        c.execute("""
            UPDATE payments SET status='approved', approved_at=?, approved_by=?
            WHERE code=?
        """, (now, admin_id, code))
        c.execute("""
            UPDATE users SET plan=?, expires_at=?, updated_at=?
            WHERE user_id=?
        """, (p["plan"], new_expires, now, p["user_id"]))
    return get_user(p["user_id"])


def reject_payment(code: str, admin_id: int, reason: str = "") -> bool:
    p = get_payment(code)
    if not p or p["status"] != "pending":
        return False
    now = int(time.time())
    with conn() as c:
        c.execute("""
            UPDATE payments SET status='rejected', rejected_reason=?, approved_at=?, approved_by=?
            WHERE code=?
        """, (reason[:500], now, admin_id, code))
    return True


def list_users_recent(limit: int = 20) -> list[dict]:
    """List most recently created users with usage stats joined."""
    with conn() as c:
        rows = c.execute("""
            SELECT u.user_id, u.username, u.first_name, u.plan, u.expires_at,
                   u.free_used, u.created_at, u.captcha_passed,
                   COALESCE((SELECT COUNT(*) FROM generations g WHERE g.user_id = u.user_id), 0) AS gen_count
            FROM users u
            ORDER BY u.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    """Aggregate stats for /stats admin command."""
    now = int(time.time())
    today_start = now - (now % 86400)  # midnight UTC today
    week_ago = now - 7 * 86400
    month_ago = now - 30 * 86400
    with conn() as c:
        # User counts
        u_total      = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        u_premium    = c.execute("SELECT COUNT(*) FROM users WHERE plan != 'free' AND expires_at > ?",
                                 (now,)).fetchone()[0]
        u_free_used  = c.execute("SELECT COUNT(*) FROM users WHERE free_used > 0").fetchone()[0]
        u_trial_full = c.execute("SELECT COUNT(*) FROM users WHERE free_used >= 3").fetchone()[0]
        u_captcha    = c.execute("SELECT COUNT(*) FROM users WHERE captcha_passed = 1").fetchone()[0]
        # New users by period
        u_today      = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?",
                                 (today_start,)).fetchone()[0]
        u_week       = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?",
                                 (week_ago,)).fetchone()[0]
        u_month      = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?",
                                 (month_ago,)).fetchone()[0]
        # Active users (gen in last 24h / 7d)
        u_active_24h = c.execute("""SELECT COUNT(DISTINCT user_id) FROM generations
                                    WHERE created_at >= ?""", (now - 86400,)).fetchone()[0]
        u_active_7d  = c.execute("""SELECT COUNT(DISTINCT user_id) FROM generations
                                    WHERE created_at >= ?""", (week_ago,)).fetchone()[0]
        # Generations
        gen_total    = c.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        gen_image    = c.execute("SELECT COUNT(*) FROM generations WHERE kind='image'").fetchone()[0]
        gen_video    = c.execute("SELECT COUNT(*) FROM generations WHERE kind='video'").fetchone()[0]
        gen_today    = c.execute("SELECT COUNT(*) FROM generations WHERE created_at >= ?",
                                 (today_start,)).fetchone()[0]
        gen_success  = c.execute("SELECT COUNT(*) FROM generations WHERE status='success'").fetchone()[0]
        gen_failed   = c.execute("SELECT COUNT(*) FROM generations WHERE status='failed'").fetchone()[0]
        # Revenue
        revenue_idr  = c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='approved'
        """).fetchone()[0]
        revenue_month = c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM payments
            WHERE status='approved' AND approved_at >= ?
        """, (month_ago,)).fetchone()[0]
        pending_pay  = c.execute("""
            SELECT COUNT(*) FROM payments WHERE status='pending' AND screenshot_id IS NOT NULL
        """).fetchone()[0]
        rejected_pay = c.execute("SELECT COUNT(*) FROM payments WHERE status='rejected'").fetchone()[0]
        approved_pay = c.execute("SELECT COUNT(*) FROM payments WHERE status='approved'").fetchone()[0]
        # Conversion rate
        conv_rate = round(approved_pay / u_total * 100, 1) if u_total > 0 else 0
    return {
        "users_total":      u_total,
        "users_premium":    u_premium,
        "users_free_used":  u_free_used,
        "users_trial_full": u_trial_full,
        "users_captcha":    u_captcha,
        "users_today":      u_today,
        "users_week":       u_week,
        "users_month":      u_month,
        "users_active_24h": u_active_24h,
        "users_active_7d":  u_active_7d,
        "gen_total":        gen_total,
        "gen_image":        gen_image,
        "gen_video":        gen_video,
        "gen_today":        gen_today,
        "gen_success":      gen_success,
        "gen_failed":       gen_failed,
        "revenue_idr":      revenue_idr,
        "revenue_month":    revenue_month,
        "pending_pay":      pending_pay,
        "approved_pay":     approved_pay,
        "rejected_pay":     rejected_pay,
        "conv_rate":        conv_rate,
    }


if __name__ == "__main__":
    init_db()
    print("DB initialized at", DB_PATH)
    print(json.dumps(stats(), indent=2))
