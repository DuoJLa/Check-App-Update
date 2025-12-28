import requests
import json
import os
from datetime import datetime, timezone

ITUNES_API = "https://itunes.apple.com/lookup"
BARK_API = "https://api.day.app"
TELEGRAM_API = "https://api.telegram.org/bot"

CACHE_FILE = "version_cache.json"

REGIONS = [
    "cn", "us", "hk", "tw", "jp", "kr", "gb", "sg", "au",
    "de", "fr", "ca", "it", "es", "ru", "br", "mx", "in", "th", "vn"
]

REGION_NAMES = {
    "cn": "中国", "us": "美国", "hk": "香港", "tw": "台湾", "jp": "日本",
    "kr": "韩国", "gb": "英国", "sg": "新加坡", "au": "澳大利亚",
    "de": "德国", "fr": "法国", "ca": "加拿大", "it": "意大利",
    "es": "西班牙", "ru": "俄罗斯", "br": "巴西", "mx": "墨西哥",
    "in": "印度", "th": "泰国", "vn": "越南",
}


def get_push_method():
    return os.getenv("PUSH_METHOD", "bark").lower()


def get_bark_key():
    return os.getenv("BARK_KEY", "")


def get_telegram_config():
    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", "")
    }


def get_app_ids():
    ids = os.getenv("APP_IDS", "")
    return [i.strip() for i in ids.split(",") if i.strip()]


def load_version_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            print("📂 缓存文件不存在，本次视为首次运行")
            return {}
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                print(f"📂 已加载缓存库，共 {len(data)} 条记录")
                return data
            print("⚠️ 缓存文件格式异常，将视为空缓存")
            return {}
    except Exception as e:
        print(f"⚠️ 加载缓存库失败，将视为空缓存: {e}")
        return {}


def save_version_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"💾 缓存库已写入本地文件（{len(cache)} 条记录）")
    except Exception as e:
        print(f"❌ 保存缓存库失败: {e}")


def get_app_info_with_region(app_id: str):
    for region in REGIONS:
        try:
            resp = requests.get(
                ITUNES_API,
                params={"id": app_id, "country": region},
                timeout=10
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get("resultCount", 0) > 0:
                app = data["results"][0]
                app["detected_region"] = region
                print(f"✓ 在 {REGION_NAMES.get(region, region)} 区找到应用 {app_id}")
                return app
        except Exception as e:
            print(f"查询 {app_id} 地区 {region} 失败: {e}")
    print(f"✗ 在所有地区未找到应用 {app_id}")
    return None


def format_datetime(iso_datetime: str) -> str:
    if not iso_datetime:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
        local_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return local_dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_datetime


def send_bark_notification(bark_key, title, content, url=None, icon_url=None):
    try:
        data = {
            "title": title,
            "body": content,
            "group": "App Store更新",
            "sound": "bell",
            "isArchive": "1",
        }
        if url:
            data["url"] = url
        if icon_url:
            data["icon"] = icon_url

        resp = requests.post(f"{BARK_API}/{bark_key}", data=data, timeout=10)
        if resp.status_code == 200:
            print("✅ Bark 推送成功")
            return True
        print(f"❌ Bark 推送失败，状态码 {resp.status_code}，响应：{resp.text}")
    except Exception as e:
        print(f"❌ Bark 推送异常: {e}")
    return False


def send_telegram_notification(bot_token, chat_id, title, content):
    try:
        message = f"*{title}*\n\n{content}"
        url = f"{TELEGRAM_API}{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("ok"):
            print("✅ Telegram 推送成功")
            return True
        print(f"❌ Telegram 推送失败: {data.get('description')}")
    except Exception as e:
        print(f"❌ Telegram 推送异常: {e}")
    return False


def send_notification(title, content, url=None, icon_url=None):
    method = get_push_method()
    if method == "bark":
        key = get_bark_key()
        if not key:
            print("❌ 未配置 BARK_KEY")
            return False
        return send_bark_notification(key, title, content, url, icon_url)
    elif method == "telegram":
        cfg = get_telegram_config()
        if not cfg["bot_token"] or not cfg["chat_id"]:
            print("❌ 未配置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
            return False
        return send_telegram_notification(cfg["bot_token"], cfg["chat_id"], title, content)
    else:
        print(f"❌ 不支持的推送方式: {method}")
        return False


def check_updates():
    app_ids = get_app_ids()
    if not app_ids:
        print("❌ 未配置 APP_IDS")
        return

    method = get_push_method()
    print(f"📢 推送方式: {method}")
    print(f"📱 监控应用数量: {len(app_ids)}")
    print("=" * 50)

    cache = load_version_cache()
    is_first_run = len(cache) == 0
    print(f"🔁 是否首次运行: {is_first_run}")

    all_current_apps = []
    updated_apps = []

    for app_id in app_ids:
        print(f"\n🔍 检查应用 ID: {app_id}")
        info = get_app_info_with_region(app_id)
        if not info:
            continue

        name = info.get("trackName", "Unknown")
        version = info.get("version", "0.0.0")
        notes = info.get("releaseNotes", "无更新说明")
        url = info.get("trackViewUrl", "")
        release_iso = info.get("currentVersionReleaseDate", "")
        region_code = info.get("detected_region", "us")
        region_name = REGION_NAMES.get(region_code, region_code.upper())
        icon = info.get("artworkUrl100", "")

        release_time = format_datetime(release_iso)
        old_version = cache.get(app_id, {}).get("version", "")

        if is_first_run:
            print(f"📝 初始化: {name} v{version} - {region_name}")
            all_current_apps.append(
                {
                    "id": app_id,
                    "name": name,
                    "version": version,
                    "notes": notes,
                    "release": release_time,
                    "url": url,
                    "icon": icon,
                    "region": region_name,
                }
            )
            cache[app_id] = {
                "version": version,
                "app_name": name,
                "region": region_code,
                "icon": icon,
                "updated_at": datetime.now().isoformat(),
            }
        else:
            if old_version != version:
                print(f"🎉 检测到更新: {name} {old_version or '无'} → {version}")
                updated_apps.append(
                    {
                        "id": app_id,
                        "name": name,
                        "old_version": old_version or "首次检测",
                        "version": version,
                        "notes": notes,
                        "release": release_time,
                        "url": url,
                        "icon": icon,
                        "region": region_name,
                    }
                )
                cache[app_id] = {
                    "version": version,
                    "app_name": name,
                    "region": region_code,
                    "icon": icon,
                    "updated_at": datetime.now().isoformat(),
                }
            else:
                print(f"✓ 无更新: {name} v{version} - {region_name}")

    print("\n" + "=" * 50)

    if is_first_run:
        if not all_current_apps:
            print("⚠️ 首次运行未获取到任何应用信息，跳过推送")
            return

        title = f"📱 App Store 监控初始化（{len(all_current_apps)} 个应用）"
        parts = []
        for i, app in enumerate(all_current_apps, 1):
            part = (
                f"{i}. *{app['name']}* v{app['version']}\n"
                f"   地区: {app['region']} | 更新时间: {app['release']}\n"
                f"   {app['notes'][:80]}{'...' if len(app['notes']) > 80 else ''}\n"
            )
            parts.append(part)
        content = "首次运行，已创建缓存库，当前应用版本如下：\n\n" + "\n".join(parts)

        first = all_current_apps[0]
        if method == "bark":
            send_notification(title, content, first["url"], first["icon"])
        else:
            links = "\n".join([f"🔗 [{a['name']}]({a['url']})" for a in all_current_apps])
            send_notification(title, content + "\n" + links)

        save_version_cache(cache)
        return

    # 非首次运行
    if not updated_apps:
        print("😴 所有应用均为最新版本，无需推送")
        return

    print(f"📦 本次有 {len(updated_apps)} 个应用更新")

    if len(updated_apps) == 1:
        app = updated_apps[0]
        title = f"📱 {app['name']} 已更新"
        content = (
            f"版本: {app['version']}\n"
            f"地区: {app['region']}\n"
            f"更新时间: {app['release']}\n\n"
            f"更新内容:\n{app['notes'][:300]}"
        )
        if method == "bark":
            send_notification(title, content, app["url"], app["icon"])
        else:
            content += f"\n\n🔗 [{app['name']}]({app['url']})"
            send_notification(title, content)
    else:
        title = f"📱 App Store 更新通知（{len(updated_apps)} 个应用）"
        parts = []
        for i, app in enumerate(updated_apps, 1):
            part = (
                f"{i}. *{app['name']}* {app['old_version']} → {app['version']}\n"
                f"   地区: {app['region']} | 更新时间: {app['release']}\n"
                f"   {app['notes'][:100]}{'...' if len(app['notes']) > 100 else ''}\n"
            )
            parts.append(part)
        content = "\n".join(parts)
        if method == "bark":
            first = updated_apps[0]
            send_notification(title, content, first["url"], first["icon"])
        else:
            links = "\n".join([f"🔗 [{a['name']}]({a['url']})" for a in updated_apps])
            send_notification(title, content + "\n\n" + links)

    save_version_cache(cache)


if __name__ == "__main__":
    check_updates()
