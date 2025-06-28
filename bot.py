import logging
import paramiko
import threading
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters,
    ConversationHandler, ContextTypes
)

# --- Ayarlar ---
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKENINIZI_BURAYA"
ALLOWED_USERS = [123456789]  # İzin verilen Telegram ID'ler

# Conversation adımları
IP, USER, PASSWORD, CERT = range(4)

# Loglama
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

async def unauthorized(update: Update):
    await update.message.reply_text("🚫 Yetkiniz yok.")
    return ConversationHandler.END

# --- Komutlara Başlangıç ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return await unauthorized(update)
    await update.message.reply_text("📥 Lütfen VPS IP adresini girin:")
    return IP

async def get_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ip'] = update.message.text.strip()
    await update.message.reply_text("👤 Kullanıcı adı (örneğin root) girin:")
    return USER

async def get_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['user'] = update.message.text.strip()
    await update.message.reply_text("🔑 Şifreyi girin:")
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['password'] = update.message.text.strip()
    await update.message.reply_text(
        "📜 Sertifikayı tam blok halinde gönderin (-----BEGIN...END CERTIFICATE-----):"
    )
    return CERT

async def get_cert_and_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cert'] = update.message.text
    await update.message.reply_text("⏳ Kurulum başlatılıyor, lütfen bekleyin...")
    # SSH işlemlerini ayrı bir thread'de yapalım
    threading.Thread(target=ssh_and_setup, args=(update, context)).start()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ İşlem iptal edildi.")
    return ConversationHandler.END

# --- SSH ile Kurulum Fonksiyonu ---
def ssh_and_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = context.user_data['ip']
    user = context.user_data['user']
    pwd = context.user_data['password']
    cert = context.user_data['cert']

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=user, password=pwd, timeout=30)

        def run(cmd):
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            return exit_status, stdout.read().decode(), stderr.read().decode()

        # 1. güncelleme
        run("sudo apt-get update && sudo apt-get upgrade -y")
        # 2. paketler
        run("sudo apt install socat curl git -y")
        # 3. klon
        run("git clone https://github.com/Gozargah/Marzban-node")
        # 4. dizine gir
        run("cd Marzban-node")
        # 5. Docker
        run("sudo curl -fsSL https://get.docker.com | sh")
        # 6. dizin oluştur
        run("sudo mkdir -p /var/lib/marzban-node/")
        # 7. sertifika yaz
        sftp = ssh.open_sftp()
        remote_cert = "/var/lib/marzban-node/ssl_client_cert.pem"
        with sftp.file(remote_cert, "w") as f:
            f.write(cert)
        sftp.close()
        # 8. docker-compose.yml yaz
        docker_compose = """
services:
  marzban-node:
    image: gozargah/marzban-node:latest
    restart: always
    network_mode: host

    volumes:
      - /var/lib/marzban-node:/var/lib/marzban-node

environment:
      SSL_CLIENT_CERT_FILE: "/var/lib/marzban-node/ssl_client_cert.pem"
      SERVICE_PROTOCOL: rest
"""
        sftp = ssh.open_sftp()
        with sftp.file("docker-compose.yml", "w") as f:
            f.write(docker_compose)
        sftp.close()
        # 9. ayağa kaldır
        run("sudo docker compose up -d")

        ssh.close()
        # Başarı mesajı
        update.message.reply_text("✅ Marzban node kurulumu tamamlandı, Node hazır!")
    except Exception as e:
        logger.exception(e)
        update.message.reply_text(f"❌ Kurulum sırasında hata: {e}")

# --- Botu Başlat ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            IP:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip)],
            USER:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            CERT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cert_and_deploy)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))

    print("🤖 Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
