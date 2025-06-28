import os
import json
import requests
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Bot tokenınızı buraya ekleyin
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
# Admin kullanıcı ID'leri
ADMINS = [123456789]  # Admin ID'lerini buraya ekleyin

# Veri depolama dosyası
IPS_JSON = "ips.json"

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update.message.reply_text(
        f"Merhaba {user.first_name}! 👋\n\n"
        "Ben WHOIS IP Bot'um. Bana bir IP adresi gönder, sana detaylı bilgiler vereyim.\n\n"
        "Örnek: `91.99.150.157` şeklinde IP gönderebilirsin.",
        parse_mode="Markdown"
    )

def get_whois_info(ip: str) -> dict:
    """IP adresi için WHOIS bilgilerini al"""
    try:
        # IPAPI kullanarak bilgileri al
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,reverse,mobile,proxy,hosting,query")
        data = response.json()

        if data.get("status") == "success":
            # AS numarasını formatla
            as_number = "N/A"
            if data.get("as"):
                as_parts = data.get("as", "").split(' ')
                if as_parts:
                    as_number = as_parts[0]

            # Cloudflare bilgisini al
            cloudflare_response = "N/A"
            try:
                cf_response = requests.get(f"https://www.cloudflare.com/cdn-cgi/trace?ip={ip}")
                if "ip=" in cf_response.text:
                    cloudflare_response = cf_response.text.split("\n")[1].split("=")[1]
            except:
                pass

            return {
                "ip": ip,
                "reverse": data.get("reverse", "N/A"),
                "country": data.get("country", "N/A"),
                "city": data.get("city", "N/A"),
                "region": data.get("regionName", "N/A"),
                "provider": f"{data.get('isp', 'N/A')} (AS{as_number})",
                "organization": data.get("org", "N/A"),
                "timezone": data.get("timezone", "N/A"),
                "coordinates": f"{data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}",
                "mobile": data.get("mobile", False),
                "proxy": data.get("proxy", False),
                "hosting": data.get("hosting", False),
                "cloudflare": cloudflare_response
            }
        else:
            return {"error": data.get("message", "Bilinmeyen hata")}
    except Exception as e:
        return {"error": str(e)}

def save_ip_data(user_id: int, username: str, ip: str):
    """IP sorgusunu kaydet"""
    now = datetime.now()
    data = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "username": username,
        "ip": ip
    }

    # Eski verileri oku veya yeni liste oluştur
    try:
        with open(IPS_JSON, "r") as f:
            existing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = []

    # Yeni veriyi ekle
    existing_data.append(data)

    # Dosyaya yaz
    with open(IPS_JSON, "w") as f:
        json.dump(existing_data, f, indent=2)

def handle_ip(update: Update, context: CallbackContext) -> None:
    """Kullanıcıdan gelen IP'yi işle"""
    ip = update.message.text.strip()
    
    # Basit IP doğrulama
    parts = ip.split('.')
    if len(parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        update.message.reply_text("Geçersiz IP adresi formatı. Lütfen doğru bir IPv4 adresi girin.")
        return

    # WHOIS bilgilerini al
    whois_info = get_whois_info(ip)
    
    if "error" in whois_info:
        update.message.reply_text(f"Hata: {whois_info['error']}")
        return

    # Kullanıcı bilgilerini kaydet
    user = update.effective_user
    save_ip_data(user.id, user.username, ip)

    # Formatlı mesaj oluştur
    message = (
        f"🌐 *WHOIS Bilgileri* 🌐\n\n"
        f"• *IP:* `{whois_info['ip']}`\n"
        f"• *Reverse DNS:* `{whois_info['reverse']}`\n"
        f"• *Ülke:* {whois_info['country']}\n"
        f"• *Şehir:* {whois_info['city']}, {whois_info['region']}\n"
        f"• *Saat Dilimi:* {whois_info['timezone']}\n"
        f"• *Koordinatlar:* {whois_info['coordinates']}\n"
        f"• *Provider:* {whois_info['provider']}\n"
        f"• *Kuruluş:* {whois_info['organization']}\n"
        f"• *Cloudflare Yanıtı:* `{whois_info['cloudflare']}`\n\n"
        f"*Ek Bilgiler:*\n"
        f"• Mobil: {'✅' if whois_info['mobile'] else '❌'}\n"
        f"• Proxy/VPN: {'✅' if whois_info['proxy'] else '❌'}\n"
        f"• Hosting: {'✅' if whois_info['hosting'] else '❌'}\n\n"
        f"@{user.username if user.username else 'N/A'} ✅\n"
        f"_{datetime.now().strftime('%d %B %H:%M')}_"
    )

    # Mesajı gönder
    update.message.reply_text(message, parse_mode="Markdown")

def send_ip_data(update: Update, context: CallbackContext) -> None:
    """Adminlere son 24 saatte sorgulanan IP'leri gönder"""
    user = update.effective_user
    
    if user.id not in ADMINS:
        update.message.reply_text("⛔ Bu komut sadece yöneticiler için.")
        return

    try:
        # Son 24 saatteki verileri filtrele
        cutoff = datetime.now() - timedelta(hours=24)
        
        with open(IPS_JSON, "r") as f:
            all_data = json.load(f)
        
        recent_data = [
            entry for entry in all_data 
            if datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S") >= cutoff
        ]

        # Geçici dosya oluştur
        temp_file = "recent_ips.json"
        with open(temp_file, "w") as f:
            json.dump(recent_data, f, indent=2)

        # Dosyayı gönder
        with open(temp_file, "rb") as f:
            update.message.reply_document(
                document=f,
                filename="recent_ips.json",
                caption="Son 24 saatte sorgulanan IP'ler:"
            )

        # Geçici dosyayı sil
        os.remove(temp_file)
    except Exception as e:
        update.message.reply_text(f"Dosya gönderilirken hata oluştu: {e}")

def main() -> None:
    """Botu başlat"""
    updater = Updater(TOKEN)

    # Komut işleyicileri
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("data", send_ip_data))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_ip))

    # Botu başlat
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    # JSON dosyasını kontrol et veya oluştur
    if not os.path.exists(IPS_JSON):
        with open(IPS_JSON, "w") as f:
            json.dump([], f)
    
    main()
