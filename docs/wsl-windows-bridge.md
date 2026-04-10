# WSL and Windows Proton Bridge

This setup is for operators who run Proton Mail Bridge on Windows and run MailOps inside WSL.

## Recommendation

Keep Proton Mail Bridge on Windows and let MailOps run inside WSL.

Do not make Proton Bridge inside WSL the default path. Bridge depends on OS credential storage and desktop integration, while WSL is not a normal Linux desktop session. MailOps supports the practical topology instead: Bridge on the Windows host, MailOps in WSL.

## How MailOps Finds Bridge

MailOps always tries the configured Bridge host first.

For the default Proton Bridge host, that means:

```bash
127.0.0.1:1143
```

When MailOps is running inside WSL and `127.0.0.1` cannot be opened, the Proton adapter also tries the Windows host IP detected from WSL networking files such as `/etc/resolv.conf` and `/proc/net/route`.

This means the same saved Proton profile can work in both of these cases:

- WSL mirrored networking, where Windows localhost is reachable as `127.0.0.1`
- WSL NAT networking, where Windows services may need the Windows host IP

## Check Your Setup

Run:

```bash
mailops doctor
```

Relevant rows:

- `wsl`: whether MailOps thinks it is running inside WSL
- `proton_bridge_hosts`: host candidates MailOps will try
- `proton_imap:<host>`: whether Bridge IMAP is reachable on port `1143`
- `proton_smtp:<host>`: whether Bridge SMTP is reachable on port `1025`

No credentials are sent by these checks. They only open a TCP connection.

## Connect and Sync

Save non-secret profile metadata:

```bash
mailops connect proton \
  --username operator@example.com \
  --account-email operator@example.com \
  --save-profile work
```

Verify folders:

```bash
MAILOPS_PROTON_PASSWORD=bridge-password mailops connect proton --profile work --list-folders
```

Sync a bounded slice:

```bash
MAILOPS_PROTON_PASSWORD=bridge-password mailops sync --provider proton --profile work --folder "All Mail" --limit 50
```

Create and review drafts locally:

```bash
mailops ask "draft replies for scheduling emails from this week"
mailops review batch list
mailops review batch show batch_xxxxxxxx
```

Apply a reviewed draft batch to Proton Drafts:

```bash
MAILOPS_PROTON_PASSWORD=bridge-password mailops apply batch_xxxxxxxx
```

## Troubleshooting

If `mailops doctor` shows `127.0.0.1` as unreachable but a Windows host IP as reachable, MailOps should work without extra flags.

If all Bridge hosts are unreachable:

- confirm Proton Mail Bridge is running on Windows
- confirm Bridge shows IMAP port `1143` and SMTP port `1025`
- confirm Windows firewall is not blocking WSL access to Bridge
- try WSL mirrored networking if your Windows and WSL versions support it
- run MailOps from Windows Python for provider write-path validation if Windows only exposes Bridge on its own loopback interface

Some Windows setups expose Bridge only to Windows `127.0.0.1`. In that case, MailOps in WSL can detect the problem, but it cannot force Windows Bridge to listen on an address WSL can reach. Use Windows Python, WSL mirrored networking, or an explicit Windows port-forwarding setup.

If Bridge is reachable but login fails:

- use the Bridge-generated IMAP username and password, not your Proton account password
- rotate the Bridge password if it has been pasted into logs or chat
- pass the password only at runtime with `MAILOPS_PROTON_PASSWORD` or `--password`

## Current Boundary

This WSL mode is supported:

```text
MailOps in WSL -> Proton Bridge on Windows -> Proton Mail
```

This mode is experimental and not the default recommendation:

```text
Proton Bridge inside WSL
```
