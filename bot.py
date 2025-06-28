#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEEZER IP Checker Telegram Bot
"""

import os
import sys
import requests
import socket
import time
import nmap
import ping3
from datetime import datetime
from colorama import init, Fore, Back, Style
from pyfiglet import Figlet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

init(autoreset=True)
f = Figlet(font='slant')

class DeezerIPCheckerBot:
    def __init__(self, token):
        self.token = token
        self.updater = Updater(token=self.token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        # Komut işleyicileri
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("ipinfo", self.ip_info_command))
        self.dispatcher.add_handler(CommandHandler("ping", self.ping_command))
        self.dispatcher.add_handler(CommandHandler("nmap", self.nmap_command))
        self.dispatcher.add_handler(CommandHandler("myip", self.myip_command))
        
        # Buton işleyicileri
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
        
    def start(self, update: Update, context: CallbackContext):
        """Botu başlatan komut"""
        keyboard = [
            [InlineKeyboardButton("IP Bilgisi", callback_data='ipinfo'),
             InlineKeyboardButton("Site Ping", callback_data='ping')],
            [InlineKeyboardButton("Nmap Tarama", callback_data='nmap'),
             InlineKeyboardButton("IP'mi Göster", callback_data='myip')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"*DEEZER IP Checker Botuna Hoş Geldiniz!*\n\n"
            "Aşağıdaki seçeneklerden birini seçin veya komutları kullanın:\n"
            "/ipinfo [IP] - IP bilgilerini göster\n"
            "/ping [site] - Site ping süresini ölç\n"
            "/nmap [hedef] - Nmap taraması yap\n"
            "/myip - Kendi IP'nizi göster\n\n"
            "Örnek: `/ipinfo 8.8.8.8`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def button_handler(self, update: Update, context: CallbackContext):
        """Inline buton işleyici"""
        query = update.callback_query
        query.answer()
        
        if query.data == 'ipinfo':
            query.edit_message_text("Lütfen bir IP adresi girin. Örnek: /ipinfo 8.8.8.8")
        elif query.data == 'ping':
            query.edit_message_text("Lütfen bir site adresi girin. Örnek: /ping google.com")
        elif query.data == 'nmap':
            query.edit_message_text("Lütfen tarama yapılacak hedefi girin. Örnek: /nmap example.com")
        elif query.data == 'myip':
            self.check_my_ip(update, context)
    
    def send_message(self, update: Update, context: CallbackContext, message: str):
        """Mesaj gönderme yardımcı fonksiyonu"""
        if update.callback_query:
            update.callback_query.edit_message_text(text=message, parse_mode='Markdown')
        else:
            update.message.reply_text(text=message, parse_mode='Markdown')
    
    def ip_info_command(self, update: Update, context: CallbackContext):
        """IP bilgisi komutu"""
        if not context.args:
            self.send_message(update, context, "Lütfen bir IP adresi girin. Örnek: /ipinfo 8.8.8.8")
            return
            
        ip = context.args[0]
        self.get_ip_info(update, context, ip)
        self.check_cloudflare(update, context, ip)
    
    def get_ip_info(self, update: Update, context: CallbackContext, ip: str):
        """IP bilgilerini getir"""
        try:
            message = "*Fetching IP information...*\n\n"
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=66846719")
            data = response.json()
            
            if data['status'] == 'success':
                message += (
                    f"✅ *IP:* `{data['query']}`\n"
                    f"📍 *Location:* {data['country']}, {data['city']} ({data['zip']})\n"
                    f"🖥️ *ISP:* {data['isp']} | *ORG:* {data['org']}\n"
                    f"🌐 *AS:* {data['as']}\n"
                    f"🗺️ *Coordinates:* {data['lat']}, {data['lon']}\n"
                    f"⏰ *Timezone:* {data['timezone']}\n"
                    f"🛡️ *Proxy:* {data['proxy']} | *Mobile:* {data['mobile']} | *Hosting:* {data['hosting']}"
                )
            else:
                message = "❌ IP information could not be fetched"
                
            self.send_message(update, context, message)
                
        except Exception as e:
            self.send_message(update, context, f"❌ Error: {str(e)}")
            
    def check_cloudflare(self, update: Update, context: CallbackContext, domain: str):
        """Cloudflare kontrolü"""
        try:
            message = "*Checking Cloudflare...*\n"
            response = requests.get(f"https://{domain}", timeout=5)
            if "cloudflare" in response.headers.get("Server", "").lower():
                message += "☁️ *Cloudflare Detected!*"
            else:
                message += "☀️ *No Cloudflare Detected*"
                
            self.send_message(update, context, message)
        except:
            self.send_message(update, context, "❌ Cloudflare check failed")
            
    def ping_command(self, update: Update, context: CallbackContext):
        """Ping komutu"""
        if not context.args:
            self.send_message(update, context, "Lütfen bir site adresi girin. Örnek: /ping google.com")
            return
            
        domain = context.args[0]
        self.ping_site(update, context, domain)
            
    def ping_site(self, update: Update, context: CallbackContext, domain: str):
        """Site ping işlemi"""
        try:
            message = f"*Pinging {domain}...*\n\n"
            ip = socket.gethostbyname(domain)
            message += f"🔗 *Resolved IP:* `{ip}`\n\n"
            
            times = []
            for _ in range(4):
                delay = ping3.ping(ip, unit='ms')
                if delay:
                    times.append(delay)
                    message += f"⏱️ Ping: `{delay:.2f} ms`\n"
                    time.sleep(1)
                    
            if times:
                avg = sum(times) / len(times)
                message += f"\n📊 *Average Ping:* `{avg:.2f} ms`"
            else:
                message += "❌ Ping failed"
                
            self.send_message(update, context, message)
                
        except Exception as e:
            self.send_message(update, context, f"❌ Error: {str(e)}")
            
    def nmap_command(self, update: Update, context: CallbackContext):
        """Nmap komutu"""
        if not context.args:
            self.send_message(update, context, "Lütfen bir hedef girin. Örnek: /nmap example.com")
            return
            
        target = context.args[0]
        self.nmap_scan(update, context, target)
            
    def nmap_scan(self, update: Update, context: CallbackContext, ip: str):
        """Nmap taraması"""
        try:
            message = f"*Starting Nmap scan for {ip}...*\n\n"
            nm = nmap.PortScanner()
            nm.scan(hosts=ip, arguments='-T4 -F')
            
            message += "*Scan Results:*\n"
            for host in nm.all_hosts():
                message += f"\n🔍 *Host:* `{host}` ({nm[host].hostname()})\n"
                message += f"🛡️ *State:* {nm[host].state()}\n"
                
                for proto in nm[host].all_protocols():
                    message += f"\n📌 *Protocol:* {proto}\n"
                    ports = nm[host][proto].keys()
                    
                    for port in sorted(ports):
                        message += f"  ⚡ *Port {port}:* {nm[host][proto][port]['state']} | *Service:* {nm[host][proto][port]['name']}\n"
                        
            self.send_message(update, context, message)
                        
        except Exception as e:
            self.send_message(update, context, f"❌ Nmap error: {str(e)}")
            
    def myip_command(self, update: Update, context: CallbackContext):
        """Kendi IP'mi göster komutu"""
        self.check_my_ip(update, context)
            
    def check_my_ip(self, update: Update, context: CallbackContext):
        """Kendi IP'yi kontrol et"""
        try:
            message = "*Checking your public IP...*\n\n"
            response = requests.get("https://api.ipify.org?format=json")
            ip = response.json()['ip']
            
            message += f"🌐 *Your Public IP:* `{ip}`\n\n"
            self.send_message(update, context, message)
            
            # IP bilgilerini de göster
            self.get_ip_info(update, context, ip)
            
        except Exception as e:
            self.send_message(update, context, f"❌ Error: {str(e)}")
    
    def run(self):
        """Botu başlat"""
        self.updater.start_polling()
        print("Bot başlatıldı...")
        self.updater.idle()

if __name__ == "__main__":
    # Telegram bot tokenınızı buraya girin
    BOT_TOKEN = "7676326389:AAEmoFd8WabmM77OLgorxLXH5bu7UTxQEzo"
    
    try:
        bot = DeezerIPCheckerBot(BOT_TOKEN)
        bot.run()
    except KeyboardInterrupt:
        print("\nBot durduruldu...")
        sys.exit(0)
