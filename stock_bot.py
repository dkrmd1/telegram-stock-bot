#!/usr/bin/env python3
"""
Bot Telegram Saham Indonesia - Railway Ready
FINAL VERSION - NO FLOOD CONTROL ISSUES
"""

import os
import sys
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

# ===================== SIMPLE CONFIG =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", 500))
BOT_NAME = os.getenv("BOT_NAME", "AkademikSaham_AIbot")
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

POPULAR_STOCKS = {
    'BBCA.JK': 'Bank Central Asia',
    'BBRI.JK': 'Bank Rakyat Indonesia', 
    'BMRI.JK': 'Bank Mandiri',
    'TLKM.JK': 'Telkom Indonesia',
    'ASII.JK': 'Astra International',
    'UNVR.JK': 'Unilever Indonesia',
    'ICBP.JK': 'Indofood CBP',
    'KLBF.JK': 'Kalbe Farma',
    'GGRM.JK': 'Gudang Garam',
    'INDF.JK': 'Indofood Sukses Makmur',
    'GOTO.JK': 'GoTo Gojek Tokopedia',
    'BUKA.JK': 'Bukalapak'
}

# Setup logging - MINIMAL
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("yfinance").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ===================== SIMPLE BOT CLASS =====================

class StockBot:
    def __init__(self):
        self.popular_stocks = POPULAR_STOCKS
        self.stock_cache: Dict[str, tuple[dict, datetime]] = {}
        self.cache_expiry = timedelta(minutes=5)
        logger.info(f"Bot initialized with {len(self.popular_stocks)} stocks")

    async def get_stock_data(self, code: str) -> Optional[dict]:
        """Get stock data with simple caching"""
        # Check cache first
        if code in self.stock_cache:
            data, timestamp = self.stock_cache[code]
            if datetime.now() - timestamp < self.cache_expiry:
                return data

        try:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                return None
                
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            
            data = {
                'code': code,
                'name': self.popular_stocks.get(code, code.replace('.JK', '')),
                'current_price': current_price,
                'change': change,
                'change_pct': change_pct,
                'volume': hist['Volume'].iloc[-1] if not hist['Volume'].empty else 0,
            }
            
            # Cache the result
            self.stock_cache[code] = (data, datetime.now())
            return data
            
        except Exception as e:
            logger.error(f"Error getting stock data for {code}: {e}")
            return None

    # ==================== HANDLERS ====================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user.first_name
        keyboard = [
            [InlineKeyboardButton("📈 Saham Populer", callback_data='popular')],
            [InlineKeyboardButton("📊 Kondisi IHSG", callback_data='ihsg')],
            [InlineKeyboardButton("❓ Bantuan", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome = f"""🎉 Selamat datang di {BOT_NAME}, {user}!

📱 Pilih menu di bawah atau ketik kode saham langsung:
Contoh: BBCA, BBRI, GOTO"""
        
        await update.message.reply_text(welcome, reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == 'popular':
                await self.show_popular_stocks(query)
            elif query.data == 'ihsg':
                await self.show_ihsg(query)
            elif query.data == 'help':
                await self.show_help(query)
            elif query.data == 'back':
                await self.show_main_menu(query)
        except Exception as e:
            logger.error(f"Button handler error: {e}")
            await query.edit_message_text("❌ Error, silakan coba lagi")

    async def show_main_menu(self, query):
        """Show main menu"""
        keyboard = [
            [InlineKeyboardButton("📈 Saham Populer", callback_data='popular')],
            [InlineKeyboardButton("📊 Kondisi IHSG", callback_data='ihsg')],
            [InlineKeyboardButton("❓ Bantuan", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""🏠 {BOT_NAME} - Menu Utama

📱 Pilih menu di bawah atau ketik kode saham langsung"""
        
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_popular_stocks(self, query):
        """Show popular stocks"""
        await query.edit_message_text("⏳ Mengambil data saham populer...")
        
        message = "📈 **SAHAM POPULER INDONESIA**\n\n"
        
        count = 0
        for code, name in self.popular_stocks.items():
            if count >= 8:  # Limit to prevent timeout
                break
                
            data = await self.get_stock_data(code)
            if data:
                emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
                stock_code = data['code'].replace('.JK', '')
                message += f"{emoji} **{stock_code}** - {name[:18]}\n"
                message += f"   💰 Rp {data['current_price']:.0f} ({data['change_pct']:+.2f}%)\n\n"
                count += 1
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_ihsg(self, query):
        """Show IHSG data"""
        await query.edit_message_text("⏳ Mengambil data IHSG...")
        
        try:
            ihsg = yf.Ticker("^JKSE")
            hist = ihsg.history(period="2d")
            
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = current - prev
                change_pct = (change / prev * 100) if prev else 0
                
                emoji = "🟢" if change_pct >= 0 else "🔴"
                message = f"""📊 **INDEKS HARGA SAHAM GABUNGAN**

{emoji} **IHSG**: {current:.2f}
📈 **Perubahan**: {change:+.2f} ({change_pct:+.2f}%)

🕐 **Update**: {datetime.now().strftime('%H:%M:%S WIB')}"""
            else:
                message = "❌ Gagal mengambil data IHSG"
                
        except Exception as e:
            logger.error(f"IHSG error: {e}")
            message = "❌ Error mengambil data IHSG"
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_help(self, query):
        """Show help"""
        message = f"""❓ **BANTUAN {BOT_NAME}**

**Cara Menggunakan:**
• `/start` - Mulai menggunakan bot
• `/stock KODE` - Cari saham tertentu
• Pilih menu dari tombol yang tersedia
• Atau ketik kode saham langsung

**Contoh pencarian:**
• `/stock BBCA` → Info Bank BCA  
• `/stock GOTO` → Info GoTo
• Ketik: `BBRI` → Info Bank BRI

**Fitur:**
✅ Data real-time saham Indonesia
✅ Informasi IHSG
✅ Saham-saham populer
✅ Interface yang mudah digunakan

📞 **Support**: Hubungi developer jika ada kendala"""
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (stock search)"""
        text = update.message.text.upper().strip()
        
        # Check if it looks like a stock code
        if len(text) <= 6 and text.isalpha():
            code = f"{text}.JK" if not text.endswith('.JK') else text
            
            # Send loading message
            loading_msg = await update.message.reply_text("⏳ Mencari data saham...")
            
            data = await self.get_stock_data(code)
            if data:
                emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
                stock_code = data['code'].replace('.JK', '')
                
                message = f"""📊 **{data['name']}** ({stock_code})

{emoji} **Harga**: Rp {data['current_price']:.0f}
📈 **Perubahan**: {data['change_pct']:+.2f}%
📊 **Volume**: {data['volume']:,.0f}

🕐 **Update**: {datetime.now().strftime('%H:%M:%S WIB')}"""
                
                await loading_msg.edit_text(message, parse_mode='Markdown')
            else:
                await loading_msg.edit_text(f"❌ Saham **{text}** tidak ditemukan", parse_mode='Markdown')

# ===================== MAIN FUNCTION =====================

def main():
    """Main function - Railway Variables Required"""
    
    print("Checking Railway environment variables...")
    print(f"TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
    print(f"BOT_NAME: {BOT_NAME}")
    
    if not TELEGRAM_BOT_TOKEN:
        print("\n❌ TELEGRAM_BOT_TOKEN tidak ditemukan!")
        print("\n🔧 Cara fix di Railway:")
        print("1. Buka Railway dashboard")
        print("2. Pilih project Anda")
        print("3. Klik service 'worker'")
        print("4. Klik tab 'Variables'")
        print("5. Klik 'New Variable'")
        print("6. Name: TELEGRAM_BOT_TOKEN")
        print("7. Value: token dari BotFather")
        print("8. Save dan redeploy")
        sys.exit(1)
    
    print(f"🚀 Starting {BOT_NAME}...")
    print(f"🤖 Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    bot = StockBot()
    
    # Register handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("ask", bot.ask_command))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    # Run bot
    try:
        print("🔄 Starting polling mode")
        app.run_polling(drop_pending_updates=True)
            
    except KeyboardInterrupt:
        print("⏹️ Bot stopped")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()