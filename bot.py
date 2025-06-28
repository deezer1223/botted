import os
import json
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
    Application
)

# Config
TOKEN = os.getenv("7676326389:AAEmoFd8WabmM77OLgorxLXH5bu7UTxQEzo")
ADMINS = list(map(int, os.getenv("12345678", "").split(","))) if os.getenv("12345678") else []
IPS_JSON = "ips.json"

async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Merhaba {user.first_name}! 👋\n\n"
        "Ben WHOIS IP Bot'um. Bana bir IP adresi gönder, sana detaylı bilgiler vereyim.\n\n"
        "Örnek: `91.99.150.157` şeklinde IP gönderebilirsin.",
        parse_mode="Markdown"
    )

def get_whois_info(ip: str) -> dict:
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,regionName,city,isp,org,as,reverse,mobile,proxy,hosting,query")
        data = response.json()

        if data.get("status") == "success":
            as_number = "N/A"
            if data.get("as"):
                as_parts = data.get("as", "").split(' ')
                as_number = as_parts[0] if as_parts else "N/A"

            return {
                "ip": ip,
                "reverse": data.get("reverse", "N/A"),
                "country": data.get("country", "N/A"),
                "city": data.get("city", "N/A"),
                "region": data.get("regionName", "N/A"),
                "provider": f"{data.get('isp', 'N/A')} (AS{as_number})",
                "organization": data.get("org", "N/A"),
                "mobile": data.get("mobile", False),
                "proxy": data.get("proxy", False),
                "hosting": data.get("hosting", False)
            }
        return {"error": data.get("message", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}

def save_ip_data(user_id: int, username: str, ip: str):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "username": username,
        "ip": ip
    }
    
    try:
        with open(IPS_JSON, "r+") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
            data.append(entry)
            f.seek(0)
            json.dump(data, f, indent=2)
    except FileNotFoundError:
        with open(IPS_JSON, "w") as f:
            json.dump([entry], f, indent=2)

async def handle_ip(update: Update, context: CallbackContext) -> None:
    ip = update.message.text.strip()
    
    if not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip.split('.')) or len(ip.split('.')) != 4:
        await update.message.reply_text("❌ Geçersiz IP formatı! Örnek: 8.8.8.8")
        return

    info = get_whois_info(ip)
    if "error" in info:
        await update.message.reply_text(f"⚠️ Hata: {info['error']}")
        return

    user = update.effective_user
    save_ip_data(user.id, user.username or "N/A", ip)

    response_msg = (
        f"🔍 *WHOIS Sonuçları* 🔍\n\n"
        f"• *IP:* `{info['ip']}`\n"
        f"• *Ülke:* {info['country']}\n"
        f"• *Şehir:* {info['city']}, {info['region']}\n"
        f"• *ISP:* {info['provider']}\n"
        f"• *Organizasyon:* {info['organization']}\n"
        f"• *Reverse DNS:* `{info['reverse']}`\n\n"
        f"*Ek Bilgiler:*\n"
        f"📱 Mobil: {'✅' if info['mobile'] else '❌'}\n"
        f"🛡️ Proxy/VPN: {'✅' if info['proxy'] else '❌'}\n"
        f"🖥️ Hosting: {'✅' if info['hosting'] else '❌'}\n\n"
        f"@{user.username if user.username else 'N/A'} ⏱️ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await update.message.reply_text(response_msg, parse_mode="Markdown")

async def send_ip_data(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("⛔ Yetkiniz yok!")
        return

    cutoff = datetime.now() - timedelta(hours=24)
    try:
        with open(IPS_JSON, "r") as f:
            data = json.load(f)
            recent_ips = [entry for entry in data if datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S") >= cutoff]
            
        if not recent_ips:
            await update.message.reply_text("⚠️ Son 24 saatte kayıt bulunamadı")
            return
            
        with open("recent_ips.json", "w") as f:
            json.dump(recent_ips, f, indent=2)
        
        await update.message.reply_document(
            document=open("recent_ips.json", "rb"),
            filename="recent_ips.json",
            caption="⏳ Son 24 saatte sorgulanan IP'ler"
        )
        os.remove("recent_ips.json")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")

def main() -> None:
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("data", send_ip_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ip))
    
    # Start bot
    app.run_polling()

if __name__ == '__main__':
    if not os.path.exists(IPS_JSON):
        with open(IPS_JSON, "w") as f:
            json.dump([], f)
    main()
