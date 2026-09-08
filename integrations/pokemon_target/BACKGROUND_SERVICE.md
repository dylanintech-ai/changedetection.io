# Background collection and email

The installed macOS user LaunchAgents run independently of Codex:

| Label | Function |
|---|---|
| com.dylan.pokemon-browser-monitor | Continuous browser collector, 60-second cycles, up to two products per retailer per cycle in oldest-attempt order, automatic crash restart, persistent retailer cooldowns |
| com.dylan.pokemon-monitor-watchdog | Independent collector health check every 60 seconds |
| com.dylan.pokemon-mailer | Direct Gmail SMTP delivery every 30 seconds |

LaunchAgent plists are in `~/Library/LaunchAgents`. Runtime data and logs are in
`~/projects/pokemon-restock-alerts`. These services run when this macOS user is
logged in and the machine is awake and online. Browser collection currently
uses ordinary visible Chrome. The services resume at login. They cannot report
an outage while the whole machine is powered off or disconnected.

## One-time Gmail setup

Open `~/projects/pokemon-restock-alerts/setup-email.command`. It opens Google's
app-password page and requests the app password through a hidden Terminal
prompt. Use the `dylanwindow@gmail.com` account. Never paste the password into
chat. Google requires two-step verification; some protected accounts do not
offer app passwords. See https://support.google.com/mail/answer/185833?hl=en.

The setup authenticates against `smtp.gmail.com:465` with verified TLS, then
saves the credential to `~/.config/pokemon-restock/smtp.json` with mode 0600.
The credential is outside both Git repositories. The worker picks it up on
its next scheduled run; no Codex or paid provider is needed. Until setup
succeeds, `mail-health.json` reports `needs_setup` and local email is inactive.
The prior Codex email automation is paused to avoid competing senders.

## Delivery behavior

Stock emails require an unexpired queued OOS-to-IS event, a current IS
observation less than 180 seconds old, a matching purchase URL, and sourced
MSRP and release within two years. Checks repeat after SMTP authentication.
Stable inventory and startup baselines do not email. Collector outages and
recoveries have their own persistent incident queue, with one email per
outage and recovery. A recovery is sent only if its outage email was sent.

The worker marks messages sent only after SMTP accepts them. This means
accepted by Gmail, not proof of inbox delivery. Connection loss during a send
leaves `uncertain` status; a process crash may leave `sending`. Neither is
blindly retried, to avoid duplicate emails. Investigate those states against
Gmail Sent mail before changing them. Authentication failure keeps mail
pending and records a sanitized error in `mail-health.json`.

If email itself fails, it cannot send an immediate failure message through
the same broken channel. Local status remains available. Whole-machine
outage notification would require a separate externally hosted watchdog.

## Inspect or stop

Use `launchctl print gui/$(id -u)/com.dylan.pokemon-mailer` for scheduler state
(not running between timer ticks is normal). Inspect `mail-health.json` and
`browser-health.json` for application status. For any label above, stop it
with `launchctl bootout gui/$(id -u)/LABEL` and restore it with
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/LABEL.plist`.

The catalog is still incomplete. Installed services do not mean all recent
Pokémon products have verified coverage. Retailer challenges can still
degrade collection; the watchdog reports that rather than claiming healthy
monitoring solely because a process is alive.
