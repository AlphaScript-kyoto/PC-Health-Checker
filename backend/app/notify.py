from __future__ import annotations

from app.config import APP_NAME, BASE_URL


def notify(title: str, message: str, open_dashboard: bool = True) -> bool:
    """Show a Windows toast notification. Returns True on success."""
    try:
        from win11toast import toast

        kwargs = {
            "app_id": APP_NAME,
            "title": title,
            "body": message[:200],
        }
        if open_dashboard:
            kwargs["on_click"] = BASE_URL
        toast(**kwargs)
        return True
    except Exception:
        try:
            # Fallback: PowerShell balloon via BurntToast-less message
            import subprocess

            safe_title = title.replace("'", "")
            safe_msg = message[:180].replace("'", "")
            script = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                f"ContentType = WindowsRuntime] > $null; "
                f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$text = $template.GetElementsByTagName('text'); "
                f"$text.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null; "
                f"$text.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) | Out-Null; "
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_NAME}').Show($toast)"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return True
        except Exception:
            return False
