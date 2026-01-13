#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App Store 更新监控器 V2.0
优化版本 - 修复版本号重复读写问题
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ==================== 配置常量 ====================
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


# ==================== 数据模型 ====================
class AppInfo:
    """应用信息数据类"""
    def __init__(self, app_id: str, name: str, version: str, 
                 region: str, icon: str, notes: str, 
                 release_time: str, url: str):
        self.app_id = app_id
        self.name = name
        self.version = version
        self.region = region
        self.icon = icon
        self.notes = notes
        self.release_time = release_time
        self.url = url


class CachedVersion:
    """缓存版本数据类"""
    def __init__(self, version: str, app_name: str, region: str, 
                 icon: str, last_check: str):
        self.version = version
        self.app_name = app_name
        self.region = region
        self.icon = icon
        self.last_check = last_check

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "app_name": self.app_name,
            "region": self.region,
            "icon": self.icon,
            "last_check": self.last_check
        }

    @staticmethod
    def from_dict(data: dict) -> 'CachedVersion':
        return CachedVersion(
            version=data.get("version", ""),
            app_name=data.get("app_name", "Unknown"),
            region=data.get("region", "us"),
            icon=data.get("icon", ""),
            last_check=data.get("last_check", "")
        )


# ==================== 配置管理 ====================
class Config:
    """配置管理类"""
    @staticmethod
    def get_push_method() -> str:
        return os.getenv("PUSH_METHOD", "bark").lower()

    @staticmethod
    def get_bark_key() -> str:
        return os.getenv("BARK_KEY", "")

    @staticmethod
    def get_telegram_config() -> Dict[str, str]:
        return {
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", "")
        }

    @staticmethod
    def get_app_ids() -> List[str]:
        env_ids = os.getenv("APP_IDS", "")
        if env_ids:
            ids = [i.strip() for i in env_ids.split(",") if i.strip()]
            print(f"📋 从环境变量获取 {len(ids)} 个 App ID")
            return ids
        print("⚠️  未设置 APP_IDS")
        return []


# ==================== 缓存管理 ====================
class CacheManager:
    """缓存管理器 - 核心优化：避免不必要的写入"""
    
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.cache: Dict[str, CachedVersion] = {}
        self.modified = False  # 🔑 关键：追踪是否有修改
        
    def load(self) -> bool:
        """加载缓存，返回是否为首次运行"""
        if not os.path.exists(self.cache_file):
            print("📂 缓存文件不存在 -> 首次运行")
            return True
            
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                print("⚠️  缓存格式错误，重置为空")
                return True
                
            # 转换为数据对象
            for app_id, info in data.items():
                self.cache[app_id] = CachedVersion.from_dict(info)
                
            print(f"📂 缓存加载成功: {len(self.cache)} 个应用")
            return len(self.cache) == 0
            
        except Exception as e:
            print(f"❌ 加载缓存失败: {e}")
            return True
    
    def get_version(self, app_id: str) -> Optional[str]:
        """获取缓存的版本号"""
        cached = self.cache.get(app_id)
        return cached.version if cached else None
    
    def update(self, app_id: str, app_info: AppInfo, force: bool = False) -> bool:
        """
        更新缓存
        返回：True 表示有变化，False 表示无变化
        """
        old_version = self.get_version(app_id)
        
        # 🔑 核心优化：只在版本真正变化或强制更新时才修改
        if force or old_version != app_info.version:
            self.cache[app_id] = CachedVersion(
                version=app_info.version,
                app_name=app_info.name,
                region=app_info.region.split()[0] if " " in app_info.region else app_info.region,
                icon=app_info.icon,
                last_check=datetime.now().isoformat()
            )
            self.modified = True  # 标记已修改
            return True
        
        return False
    
    def save(self) -> bool:
        """保存缓存（仅在有修改时）"""
        if not self.modified:
            print("💾 缓存无变化，跳过保存")
            return False
            
        try:
            cache_dict = {
                app_id: cached.to_dict() 
                for app_id, cached in self.cache.items()
            }
            
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_dict, f, ensure_ascii=False, indent=2)
                
            print(f"💾 缓存已保存: {len(cache_dict)} 条记录")
            self.modified = False
            return True
            
        except Exception as e:
            print(f"❌ 保存缓存失败: {e}")
            return False


# ==================== API 查询 ====================
class AppStoreAPI:
    """App Store API 查询类"""
    
    @staticmethod
    def query_app(app_id: str) -> Optional[AppInfo]:
        """查询应用信息（智能地区识别）"""
        print(f"   🔍 查询: ", end="", flush=True)
        
        for i, region in enumerate(REGIONS[:6]):
            try:
                if i > 0:
                    print(".", end="", flush=True)
                    
                resp = requests.get(
                    ITUNES_API,
                    params={"id": app_id, "country": region},
                    timeout=8
                )
                
                if resp.status_code != 200:
                    continue
                    
                data = resp.json()
                if data.get("resultCount", 0) == 0:
                    continue
                
                # 解析应用信息
                result = data["results"][0]
                region_name = REGION_NAMES.get(region, region.upper())
                
                print(f" ✓ {region_name}")
                
                return AppInfo(
                    app_id=app_id,
                    name=result.get("trackName", "Unknown"),
                    version=result.get("version", "0.0"),
                    region=region_name,
                    icon=result.get("artworkUrl100", ""),
                    notes=result.get("releaseNotes", "暂无更新说明"),
                    release_time=AppStoreAPI._format_datetime(
                        result.get("currentVersionReleaseDate", "")
                    ),
                    url=result.get("trackViewUrl", "")
                )
                
            except Exception as e:
                continue
        
        print(" ✗ 失败")
        return None
    
    @staticmethod
    def _format_datetime(iso_datetime: str) -> str:
        """格式化时间（UTC+8）"""
        if not iso_datetime:
            return "未知"
        try:
            dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
            utc_plus_8 = dt + timedelta(hours=8)
            return utc_plus_8.strftime("%Y-%m-%d %H:%M")
        except:
            return iso_datetime[:16]


# ==================== 推送服务 ====================
class NotificationService:
    """推送服务类"""
    
    @staticmethod
    def send(title: str, content: str, url: str = "", icon: str = "") -> bool:
        """统一推送接口"""
        method = Config.get_push_method()
        
        if method == "bark":
            return NotificationService._send_bark(title, content, url, icon)
        elif method == "telegram":
            return NotificationService._send_telegram(title, content)
        else:
            print(f"⚠️  未知推送方式: {method}")
            return False
    
    @staticmethod
    def _send_bark(title: str, content: str, url: str, icon: str) -> bool:
        """Bark 推送"""
        key = Config.get_bark_key()
        if not key:
            print("⚠️  跳过推送: 未配置 BARK_KEY")
            return False
        
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
            if icon:
                data["icon"] = icon
            
            resp = requests.post(f"{BARK_API}/{key}", data=data, timeout=10)
            success = resp.status_code == 200
            print(f"📱 Bark: {'✅' if success else '❌'}")
            return success
            
        except Exception as e:
            print(f"❌ Bark 异常: {e}")
            return False
    
    @staticmethod
    def _send_telegram(title: str, content: str) -> bool:
        """Telegram 推送"""
        cfg = Config.get_telegram_config()
        if not cfg["bot_token"] or not cfg["chat_id"]:
            print("⚠️  跳过推送: Telegram配置不全")
            return False
        
        try:
            message = f"*{title}*\n\n{content}"
            url = f"{TELEGRAM_API}{cfg['bot_token']}/sendMessage"
            payload = {
                "chat_id": cfg["chat_id"],
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }
            
            resp = requests.post(url, json=payload, timeout=10)
            success = resp.json().get('ok', False)
            print(f"📱 Telegram: {'✅' if success else '❌'}")
            return success
            
        except Exception as e:
            print(f"❌ Telegram 异常: {e}")
            return False


# ==================== 消息格式化 ====================
def build_message(apps: List[Tuple[AppInfo, str]], is_init: bool = False) -> Tuple[str, str]:
    """
    构建推送消息
    返回：(title, content)
    """
    if not apps:
        return "", ""
    
    if is_init:
        # 初始化消息
        title = f"📱 监控初始化 ({len(apps)} 个应用)"
        parts = []
        for app_info, _ in apps:
            parts.append(
                f"📱 {app_info.name} v{app_info.version}\n"
                f"   {app_info.region} | {app_info.release_time}\n"
                f"   {app_info.notes[:80]}{'...' if len(app_info.notes) > 80 else ''}"
            )
        content = "✅ 已添加到监控列表:\n\n" + "\n\n".join(parts)
        
    elif len(apps) == 1:
        # 单个更新
        app_info, old_ver = apps[0]
        title = f"🔥 {app_info.name} 有新版本"
        content = (
            f"📱 {app_info.name} ({old_ver}→{app_info.version}) 📱\n"
            f"地区: {app_info.region} | 更新: {app_info.release_time}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{app_info.notes[:200]}"
        )
        
    else:
        # 多个更新
        title = f"📱 App Store 更新 ({len(apps)} 个)"
        parts = []
        for app_info, old_ver in apps:
            parts.append(
                f"📱 {app_info.name} {old_ver}→{app_info.version}\n"
                f"   {app_info.region} | {app_info.release_time}\n"
                f"   {app_info.notes[:80]}{'...' if len(app_info.notes) > 80 else ''}"
            )
        content = "发现更新:\n\n" + "\n\n".join(parts)
    
    return title, content


# ==================== 主程序 ====================
def main():
    """主程序入口"""
    print("=" * 60)
    print("🚀 App Store 更新监控器 V2.0")
    print("=" * 60)
    
    # 1. 加载配置
    app_ids = Config.get_app_ids()
    if not app_ids:
        print("❌ 错误: 没有要监控的应用")
        return
    
    print(f"📢 推送方式: {Config.get_push_method()}")
    print(f"📱 监控应用: {len(app_ids)} 个")
    print("-" * 60)
    
    # 2. 加载缓存
    cache_mgr = CacheManager()
    is_first_run = cache_mgr.load()
    
    # 3. 检查更新
    init_apps = []      # 首次运行的应用
    updated_apps = []   # 有更新的应用
    
    for idx, app_id in enumerate(app_ids, 1):
        print(f"\n[{idx}/{len(app_ids)}] {app_id}")
        
        # 查询应用信息
        app_info = AppStoreAPI.query_app(app_id)
        if not app_info:
            print("   ⚠️  跳过")
            continue
        
        # 获取缓存版本
        old_version = cache_mgr.get_version(app_id)
        
        # 判断是否需要推送
        if is_first_run:
            # 首次运行：全部添加
            print(f"   📝 初始化: {app_info.name} v{app_info.version}")
            init_apps.append((app_info, ""))
            cache_mgr.update(app_id, app_info, force=True)
            
        elif old_version != app_info.version:
            # 版本变化：推送更新
            print(f"   🎉 更新: {old_version or '无'} → {app_info.version}")
            updated_apps.append((app_info, old_version or "无"))
            cache_mgr.update(app_id, app_info)
            
        else:
            # 无变化
            print(f"   ✅ 最新: v{app_info.version}")
    
    print("\n" + "=" * 60)
    
    # 4. 发送推送
    if init_apps:
        title, content = build_message(init_apps, is_init=True)
        first_app = init_apps[0][0]
        NotificationService.send(title, content, first_app.url, first_app.icon)
        
    elif updated_apps:
        title, content = build_message(updated_apps)
        first_app = updated_apps[0][0]
        NotificationService.send(title, content, first_app.url, first_app.icon)
        
    else:
        print("😊 所有应用均为最新版本")
    
    # 5. 保存缓存（仅在有修改时）
    if cache_mgr.save():
        print("✅ 运行完成")
    else:
        print("✅ 运行完成（无需保存）")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 程序异常: {e}")
        raise
