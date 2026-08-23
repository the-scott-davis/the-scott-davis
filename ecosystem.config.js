// pm2 process definition for the nightly card rebuild.
//
//   pm2 start ecosystem.config.js
//   pm2 save && pm2 startup     # survive a reboot
//
// This is a one-shot script, not a long-running service: autorestart is off, and
// cron_restart is what actually schedules it. pm2 treats each run as the process
// starting, doing its work, and exiting cleanly.
//
// Note that a cron schedule only fires while the machine is awake. If this Mac
// sleeps overnight, a missed run is simply skipped rather than caught up later.
// launchd handles that case better -- see docs/PUBLISHING.md.
module.exports = {
  apps: [
    {
      name: "profile-card",
      script: "./scripts/nightly.sh",
      interpreter: "bash",
      cwd: __dirname,

      autorestart: false,
      cron_restart: "0 0 * * *", // midnight, local time

      out_file: "./logs/nightly.log",
      error_file: "./logs/nightly.error.log",
      merge_logs: true,
      time: true, // pm2 timestamps each line
    },
  ],
};
