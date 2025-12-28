import requests
import json
import os
from datetime import datetime, timezone

# iTunes API查询应用信息
ITUNES_API = "https://itunes.apple.com/lookup"
# Bark推送API
BARK_API = "https://api.day.app"
# Telegram Bot API
TELEGRAM_API = "https://api.telegram.org/bot"

# 常用App Store地区代码（按使用频率排序）[web:23][web:25][web:63]
REGIONS = [
    'cn',  # 中国
    'us',  # 美国
    'hk',  # 香港
    'tw',  # 台湾
    'jp',  # 日本
    'kr',  # 韩国
    'gb',  # 英国
    'sg',  # 新加坡
    'au',  # 澳大利亚
    'de',  # 德国
    'fr',  # 法国
    'ca',  # 加拿大
    'it',  # 意大利
    'es',  # 西班牙
    'ru',  # 俄罗斯
    'br',  # 巴西
    'mx',  # 墨西哥
    'in',  # 印度
    'th',  # 泰国
    'vn',  # 越南
]

# 地区名称映射（中文）
REGION_NAMES = {
    'cn': '中国', 'us': '美国', 'hk': '香港', 'tw': '台湾', 'jp': '日本',
    'kr': '韩国', 'gb': '英国', 'sg': '新加坡', 'au': '澳大利亚',
    'de': '德国', 'fr': '法国', 'ca': '加拿大', 'it': '意大利',
    'es': '西班牙', 'ru': '俄罗斯', 'br': '巴西', 'mx': '墨西哥',
    'in': '印度', 'th': '泰国', 'vn': '越南',
}

CACHE_FILE = "version_cache.json"


def get_push_method():
    """获取推送方式: bark 或 telegram"""
    return os.getenv('PUSH_METHOD', 'bark').lower()


def get_bark_key():
    """从环境变量获取Bark Key"""
    return os.getenv('BARK_KEY', '')


def get_telegram_config():
    """从环境变量获取Telegram配置"""
    return {
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
    }


def get_app_ids():
    """从环境变量获取App ID列表"""
    ids = os.getenv('APP_IDS', '')
    return [id.strip() for id in ids.split(',') if id.strip()]


def load_version_cache():
    """加载本地版本缓存（缓存库）"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"加载缓存库失败，将视为首次运行: {e}")
        return {}


def save_version_cache(cache):
    """保存版本缓存到缓存库"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存缓存库失败: {e}")


def get_app_info_with_region(app_id):
    """
    通过iTunes API获取应用信息，自动尝试不同地区。 [web:21][web:23][web:54]
    """
    for region in REGIONS:
        try:
            params = {
                'id': app_id,
                'country': region
            }
            resp = requests.get(ITUNES_API, params=params, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get('resultCount', 0) > 0:
                app_info = data['results'][0]
                app_info['detected_region'] = region
                print(f"✓ 在 {REGION_NAMES.get(region, region)} App Store 找到应用")
                return app_info
        except Exception as e:
            print(f"查询地区 {region} 时出错: {e}")
            continue

    print(f"✗ 在所有地区都未找到应用 ID: {app_id}")
    return None


def format_datetime(iso_datetime):
    """格式化ISO 8601时间为易读格式（本地时间）"""
    if not iso_datetime:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
        local_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return local_dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso_datetime


def send_bark_notification(bark_key, title, content, url=None, icon_url=None):
    """发送Bark推送通知（支持自定义图标）[web:35][web:41][web:46]"""
    try:
        data = {
            "title": title,
            "body": content,
            "group": "App Store更新",
            "sound": "bell",
            "isArchive": "1"
        }
        if url:
            data["url"] = url
        if icon_url:
            data["icon"] = icon_url

        resp = requests.post(f"{BARK_API}/{bark_key}", data=data, timeout=10)
        if resp.status_code == 200:
            print("✅ Bark推送成功")
            return True
        print(f"❌ Bark推送失败，状态码: {resp.status_code}, 响应: {resp.text}")
    except Exception as e:
        print(f"❌ Bark推送失败: {e}")
    return False


def send_telegram_notification(bot_token, chat_id, title, content):
    """发送Telegram Bot推送通知[web:11][web:16]"""
    try:
        message = f"*{title}*\n\n{content}"
        api_url = f"{TELEGRAM_API}{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        resp = requests.post(api_url, json=payload, timeout=10)
        result = resp.json()
        if result.get('ok'):
            print("✅ Telegram推送成功")
            return True
        print(f"❌ Telegram推送失败: {result.get('description', '未知错误')}")
    except Exception as e:
        print(f"❌ Telegram推送失败: {e}")
    return False


def send_notification(title, content, url=None, icon_url=None):
    """根据配置选择推送方式"""
    push_method = get_push_method()

    if push_method == 'telegram':
        cfg = get_telegram_config()
        if not cfg['bot_token'] or not cfg['chat_id']:
            print("❌ 错误: 未设置TELEGRAM_BOT_TOKEN或TELEGRAM_CHAT_ID")
            return False
        return send_telegram_notification(cfg['bot_token'], cfg['chat_id'], title, content)

    if push_method == 'bark':
        bark_key = get_bark_key()
        if not bark_key:
            print("❌ 错误: 未设置BARK_KEY")
            return False
        return send_bark_notification(bark_key, title, content, url, icon_url)

    print(f"❌ 错误: 不支持的推送方式 '{push_method}'，请使用 'bark' 或 'telegram'")
    return False


def check_updates():
    """
    检查应用更新：

    - 缓存库为空 → 首次运行：
        * 拉取所有 App 当前版本信息写入缓存库
        * 推送一条「初始化」通知，内容为所有 App 的当前版本
    - 缓存库非空 → 后续运行：
        * 对比版本，只推送版本变化的 App
    """
    app_ids = get_app_ids()
    if not app_ids:
        print("❌ 错误: 未设置APP_IDS")
        return

    push_method = get_push_method()
    print(f"📢 推送方式: {push_method.upper()}")
    print(f"📱 监控应用数量: {len(app_ids)}")
    print("=" * 60)

    cache = load_version_cache()
    is_first_run = (len(cache) == 0)
    if is_first_run:
        print("🆕 检测到缓存库为空，本次视为首次运行，将初始化所有应用版本信息。")

    updated_apps = []      # 非首次运行：有更新的应用
    all_current_apps = []  # 首次运行：所有应用当前状态

    for app_id in app_ids:
        print(f"\n🔍 检查应用: {app_id}")
        app_info = get_app_info_with_region(app_id)
        if not app_info:
            print("⚠️  无法获取应用信息")
            continue

        app_name = app_info.get('trackName', 'Unknown')
        current_version = app_info.get('version', '0.0.0')
        release_notes = app_info.get('releaseNotes', '无更新说明')
        app_url = app_info.get('trackViewUrl', '')
        release_date = app_info.get('currentVersionReleaseDate', '')
        region = app_info.get('detected_region', 'us')
        region_name = REGION_NAMES.get(region, region.upper())
        app_icon = app_info.get('artworkUrl100', '')  # 图标URL [web:31][web:40]

        formatted_date = format_datetime(release_date)
        cached_version = cache.get(app_id, {}).get('version', '')

        if is_first_run:
            # 首次运行：全部写入缓存，并组成初始化列表
            print(f"📝 初始化: {app_name} v{current_version} - {region_name}")
            app_status = {
                'app_id': app_id,
                'app_name': app_name,
                'version': current_version,
                'release_notes': release_notes,
                'release_date': formatted_date,
                'app_url': app_url,
                'app_icon': app_icon,
                'region': region_name
            }
            all_current_apps.append(app_status)

            cache[app_id] = {
                'version': current_version,
                'app_name': app_name,
                'region': region,
                'icon': app_icon,
                'updated_at': datetime.now().isoformat()
            }
        else:
            # 后续运行：仅对比版本
            if cached_version != current_version:
                print(f"🎉 检测到更新: {app_name}")
                print(f"   版本: {cached_version or '无'} -> {current_version}")
                print(f"   地区: {region_name}")
                print(f"   更新时间: {formatted_date}")
                update_info = {
                    'app_id': app_id,
                    'app_name': app_name,
                    'old_version': cached_version if cached_version else '首次检测',
                    'new_version': current_version,
                    'release_notes': release_notes,
                    'release_date': formatted_date,
                    'app_url': app_url,
                    'app_icon': app_icon,
                    'region': region_name
                }
                updated_apps.append(update_info)

                cache[app_id] = {
                    'version': current_version,
                    'app_name': app_name,
                    'region': region,
                    'icon': app_icon,
                    'updated_at': datetime.now().isoformat()
                }
            else:
                print(f"✓ 无更新: {app_name} (v{current_version}) - {region_name}")

    print("\n" + "=" * 60)

    if is_first_run:
        # 首次运行：推送所有应用当前版本
        if not all_current_apps:
            print("⚠️ 首次运行没有成功获取到任何应用信息，跳过推送。")
            return

        title = f"📱 App Store 监控初始化完成（{len(all_current_apps)} 个应用）"
        parts = []
        for i, app in enumerate(all_current_apps, 1):
            part = (
                f"{i}. *{app['app_name']}* v{app['version']}\n"
                f"   地区: {app['region']} | 更新时间: {app['release_date']}\n"
                f"   {app['release_notes'][:80]}{'...' if len(app['release_notes']) > 80 else ''}\n"
            )
            parts.append(part)

        content = "本次为首次运行，已创建缓存库，当前各应用最新版本如下：\n\n" + "\n".join(parts)

        if push_method == 'bark':
            first_app = all_current_apps[0]
            send_notification(
                title,
                content,
                url=first_app['app_url'],
                icon_url=first_app['app_icon']
            )
        else:
            links = "\n".join(
                [f"🔗 [{app['app_name']}]({app['app_url']})" for app in all_current_apps]
            )
            content += f"\n{links}"
            send_notification(title, content)

        save_version_cache(cache)
        print("💾 缓存库已初始化并保存。")
        return

    # 非首次运行：只推送有更新的应用
    if not updated_apps:
        print("😴 所有应用均为最新版本，无需推送。")
        return

    print(f"\n📦 本次共有 {len(updated_apps)} 个应用有更新。")

    if len(updated_apps) == 1:
        app = updated_apps[0]
        title = f"📱 {app['app_name']} 已更新"
        content = (
            f"版本: {app['new_version']}\n"
            f"地区: {app['region']}\n"
            f"更新时间: {app['release_date']}\n\n"
            f"更新内容:\n{app['release_notes'][:300]}"
        )
        if push_method == 'bark':
            send_notification(title, content, app['app_url'], app['app_icon'])
        else:
            content += f"\n\n🔗 [{app['app_name']}]({app['app_url']})"
            send_notification(title, content)
    else:
        title = f"📱 App Store 更新通知（{len(updated_apps)} 个应用）"
        parts = []
        for i, app in enumerate(updated_apps, 1):
            part = (
                f"{i}. *{app['app_name']}* {app['old_version']} → {app['new_version']}\n"
                f"   地区: {app['region']} | 更新时间: {app['release_date']}\n"
                f"   {app['release_notes'][:100]}{'...' if len(app['release_notes']) > 100 else ''}\n"
            )
            parts.append(part)
        content = "\n".join(parts)

        if push_method == 'bark':
            first_app = updated_apps[0]
            send_notification(
                title,
                content,
                url=first_app['app_url'],
                icon_url=first_app['app_icon']
            )
        else:
            links = "\n".join(
                [f"🔗 [{app['app_name']}]({app['app_url']})" for app in updated_apps]
            )
            content += f"\n\n{links}"
            send_notification(title, content)

    save_version_cache(cache)
    print("💾 缓存库已更新。")


if __name__ == '__main__':
    check_updates()
