#!/usr/bin/env python3
"""
Bot Telegram Saham Indonesia - Railway Ready
COMPLETE VERSION WITH AI ASSISTANT
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

# ===================== COMPLETE BOT CLASS =====================

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

    # ==================== AI FUNCTIONS ====================
    
    async def ai_chat(self, user_question: str) -> str:
        """AI chat using OpenAI for stock/investment questions"""
        if not OPENAI_API_KEY:
            return "❌ AI Assistant tidak tersedia (OpenAI API key tidak dikonfigurasi)"
        
        try:
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            
            # System prompt for stock/investment focused AI
            system_prompt = """Anda adalah AI assistant ahli saham dan investasi Indonesia. Berikan jawaban yang:

1. Fokus pada saham Indonesia dan Bursa Efek Indonesia (BEI)
2. Berikan informasi edukasi investasi yang baik
3. Selalu ingatkan bahwa ini bukan nasihat investasi pribadi
4. Gunakan bahasa Indonesia yang mudah dipahami
5. Berikan contoh konkret jika relevan
6. Maksimal 500 kata per jawaban

PENTING: Selalu tambahkan disclaimer bahwa ini hanya informasi edukasi, bukan nasihat investasi."""

            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question}
                ],
                max_tokens=OPENAI_MAX_TOKENS,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            return f"🤖 **AI Assistant**\n\n{ai_response}\n\n💡 *Ini hanya informasi edukasi, bukan nasihat investasi*"
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"❌ Maaf, AI Assistant sedang bermasalah. Coba lagi nanti."

    # ==================== HANDLERS ====================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user.first_name
        keyboard = [
            [InlineKeyboardButton("📈 Saham Populer", callback_data='popular')],
            [InlineKeyboardButton("📊 Kondisi IHSG", callback_data='ihsg')],
            [InlineKeyboardButton("🤖 Tanya AI", callback_data='ai_help')],
            [InlineKeyboardButton("❓ Bantuan", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome = f"""🎉 Selamat datang di {BOT_NAME}, {user}!

📱 **Menu tersedia:**
• `/ask [pertanyaan]` - Tanya AI tentang saham/investasi
• `/stock KODE` - Cari saham tertentu
• Atau pilih tombol di bawah
• Atau ketik langsung kode saham

💡 **Contoh**: 
• `/ask Apa itu saham?`
• `/stock BBCA`
• Ketik: `GOTO`"""
        
        await update.message.reply_text(welcome, reply_markup=reply_markup)

    async def ask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ask command for AI chat"""
        if not context.args:
            message = """🤖 **AI Assistant - Tanya Apapun tentang Saham & Investasi**

**Format:** `/ask [pertanyaan Anda]`

**Contoh pertanyaan:**
• `/ask Apa itu saham?`
• `/ask Bagaimana cara memulai investasi?`
• `/ask Perbedaan saham dan obligasi?`
• `/ask Analisis fundamental vs teknikal?`
• `/ask Tips investasi untuk pemula?`
• `/ask Risiko investasi saham?`

💡 AI akan menjawab dengan fokus pada pasar saham Indonesia"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            return
        
        # Join all arguments as the question
        question = " ".join(context.args)
        
        # Show typing action
        await update.message.chat.send_action(action="typing")
        
        # Get AI response
        ai_answer = await self.ai_chat(question)
        
        # Send response
        await update.message.reply_text(ai_answer, parse_mode='Markdown')

    async def stock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stock command"""
        if not context.args:
            message = """📊 **Pencarian Saham**

**Format:** `/stock [KODE_SAHAM]`

**Contoh:**
• `/stock BBCA` - Info Bank BCA
• `/stock GOTO` - Info GoTo
• `/stock TLKM` - Info Telkom

💡 Atau langsung ketik kode saham tanpa command"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            return
        
        stock_code = context.args[0].upper()
        await self.search_stock(update, stock_code)

    async def search_stock(self, update: Update, stock_code: str):
        """Search for specific stock"""
        code = f"{stock_code}.JK" if not stock_code.endswith('.JK') else stock_code
        
        # Send loading message
        loading_msg = await update.message.reply_text("⏳ Mencari data saham...")
        
        data = await self.get_stock_data(code)
        if data:
            emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
            display_code = data['code'].replace('.JK', '')
            
            message = f"""📊 **{data['name']}** ({display_code})

{emoji} **Harga**: Rp {data['current_price']:.0f}
📈 **Perubahan**: {data['change_pct']:+.2f}%
📊 **Volume**: {data['volume']:,.0f}

🕐 **Update**: {datetime.now().strftime('%H:%M:%S WIB')}

💡 Ketik `/stock {display_code}` untuk update data"""
            
            await loading_msg.edit_text(message, parse_mode='Markdown')
        else:
            await loading_msg.edit_text(f"❌ Saham **{stock_code}** tidak ditemukan", parse_mode='Markdown')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == 'popular':
                await self.show_popular_stocks(query)
            elif query.data == 'ihsg':
                await self.show_ihsg(query)
            elif query.data == 'ai_help':
                await self.show_ai_help(query)
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
            [InlineKeyboardButton("🤖 Tanya AI", callback_data='ai_help')],
            [InlineKeyboardButton("❓ Bantuan", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""🏠 {BOT_NAME} - Menu Utama

📱 **Cara menggunakan:**
• `/ask [pertanyaan]` - Tanya AI tentang investasi
• `/stock KODE` - Cari saham tertentu  
• Atau ketik langsung kode saham
• Atau pilih menu di bawah"""
        
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_popular_stocks(self, query):
        """Show popular stocks"""
        await query.edit_message_text("⏳ Mengambil data saham populer...")
        
        message = "📈 **SAHAM POPULER INDONESIA**\n\n"
        
        count = 0
        for code, name in self.popular_stocks.items():
            if count >= 6:  # Limit to prevent timeout
                break
                
            data = await self.get_stock_data(code)
            if data:
                emoji = "🟢" if data['change_pct'] >= 0 else "🔴"
                stock_code = data['code'].replace('.JK', '')
                message += f"{emoji} **{stock_code}** - {name[:18]}\n"
                message += f"   💰 Rp {data['current_price']:.0f} ({data['change_pct']:+.2f}%)\n\n"
                count += 1
        
        if count == 0:
            message += "📊 Data saham sedang tidak tersedia\n(Yahoo Finance maintenance)\n\n"
            message += "💡 Coba tanya AI tentang saham:\n`/ask Analisis saham BBCA`"
        
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
                message = """❌ Data IHSG tidak tersedia saat ini
(Yahoo Finance sedang maintenance)

💡 Tanya AI tentang IHSG:
`/ask Apa itu IHSG dan bagaimana cara membacanya?`"""
                
        except Exception as e:
            logger.error(f"IHSG error: {e}")
            message = """❌ Error mengambil data IHSG

💡 Tanya AI tentang pasar saham:
`/ask Bagaimana kondisi pasar saham Indonesia?`"""
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_ai_help(self, query):
        """Show AI Assistant help"""
        if not OPENAI_API_KEY:
            message = "🤖 **AI Assistant**\n\n❌ AI Assistant tidak tersedia (OpenAI API key tidak dikonfigurasi di Railway Variables)"
        else:
            message = """🤖 **AI Assistant - Konsultasi Investasi & Saham**

**Cara menggunakan:**
• `/ask [pertanyaan]` - Tanya langsung ke AI
• Atau ketik pertanyaan langsung (dengan tanda tanya)

**Contoh pertanyaan:**
• `/ask Apa itu saham?`
• `/ask Bagaimana cara investasi yang aman?`
• `/ask Perbedaan saham dan reksa dana?`
• `/ask Analisis fundamental itu apa?`
• `Kapan waktu yang tepat beli saham?`

**AI ini bisa membantu:**
✅ Edukasi dasar investasi
✅ Penjelasan istilah keuangan
✅ Tips strategi investasi
✅ Analisis konsep saham
✅ Diskusi risiko investasi

⚠️ **Disclaimer**: AI memberikan informasi edukasi, bukan nasihat investasi pribadi"""
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_help(self, query):
        """Show help"""
        message = f"""❓ **BANTUAN {BOT_NAME}**

**Cara Menggunakan:**
• `/start` - Mulai menggunakan bot
• `/ask [pertanyaan]` - Tanya AI tentang saham/investasi
• `/stock KODE` - Cari saham tertentu
• Pilih menu dari tombol yang tersedia
• Atau ketik kode saham langsung

**Contoh penggunaan:**
• `/ask Apa itu saham?`
• `/stock BBCA` → Info Bank BCA  
• `/stock GOTO` → Info GoTo
• Ketik: `BBRI` → Info Bank BRI

**Contoh tanya AI:**
• `/ask Bagaimana cara investasi yang baik?`
• `/ask Analisis saham BBCA`
• `/ask Risiko investasi saham?`

**Fitur:**
✅ Data real-time saham Indonesia
✅ Informasi IHSG
✅ Saham-saham populer
✅ AI Assistant untuk konsultasi investasi
✅ Interface yang mudah digunakan

🔄 Bot akan coba mengambil data real-time
📊 Jika Yahoo Finance maintenance, akan tampil data demo
🤖 AI Assistant selalu siap membantu konsultasi investasi"""
        
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (stock search or AI chat)"""
        text = update.message.text.strip()
        
        # Check if it's a question (contains question words)
        question_words = ['apa', 'bagaimana', 'mengapa', 'kenapa', 'kapan', 'dimana', 'siapa', '?']
        is_question = any(word in text.lower() for word in question_words) or text.endswith('?')
        
        # If it looks like a question and longer than 10 characters, treat as AI chat
        if is_question and len(text) > 10:
            await update.message.chat.send_action(action="typing")
            ai_answer = await self.ai_chat(text)
            await update.message.reply_text(ai_answer, parse_mode='Markdown')
            return
        
        # Check if it looks like a stock code (short, alphabetic)
        if len(text) <= 6 and text.upper().isalpha():
            await self.search_stock(update, text.upper())
        else:
            # For other text, suggest using /ask command
            message = f"""💬 **Pesan Anda:** "{text}"

🤔 Sepertinya Anda ingin bertanya. Gunakan format:
`/ask {text}`

Atau ketik kode saham (contoh: BBCA, GOTO)"""
            
            await update.message.reply_text(message, parse_mode='Markdown')

# ===================== MAIN FUNCTION =====================

def main():
    """Main function - Railway Variables Required"""
    
    print("Checking Railway environment variables...")
    print(f"TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
    print(f"AI_API_KEY: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
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
    app.add_handler(CommandHandler("stock", bot.stock_command))
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