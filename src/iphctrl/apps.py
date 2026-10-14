"""Short names for common apps. Anything else: pass the bundle id (`iphctrl apps` lists them)."""

ALIASES = {
    "snapchat": "com.toyopagroup.picaboo",
    "instagram": "com.burbn.instagram",
    "tiktok": "com.zhiliaoapp.musically",
    "threads": "com.burbn.barcelona",
    "x": "com.atebits.Tweetie2",
    "telegram": "ph.telegra.Telegraph",
    "settings": "com.apple.Preferences",
    "photos": "com.apple.mobileslideshow",
    "camera": "com.apple.camera",
    "safari": "com.apple.mobilesafari",
}


def resolve_bundle(app: str) -> str:
    return ALIASES.get(app.lower(), app)
