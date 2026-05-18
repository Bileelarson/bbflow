module.exports = {
  apps: [
    {
      name: "imajin-bot",
      script: "bot/klein_bot.py",
      interpreter: "python3",
      cwd: __dirname,
      out_file: "logs/bot.out.log",
      error_file: "logs/bot.err.log",
      max_memory_restart: "1500M",
      restart_delay: 5000,
      max_restarts: 10,
      autorestart: true,
      env: {
        // Override in .env (preferred) or here
        // TELEGRAM_BOT_TOKEN: "...",
        // ADMIN_TELEGRAM_IDS: "...",
      },
    },
  ],
};
