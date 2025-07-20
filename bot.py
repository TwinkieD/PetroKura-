import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Получаем токен и ID администратора из переменных окружения
BOT_TOKEN = os.getenv("7635754983:AAEoLA9QU0Aebg-M7a7NjRkZWUPKK5JrWaY")
ADMIN_CHAT_ID = int(os.getenv("7569576915"))

# Создание бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище для заказов
user_data = {}

# Стартовая клавиатура
def start_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🛒 Новый заказ")
    return kb.as_markup(resize_keyboard=True)

# Клавиатура для отмены и возврата
def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔙 Назад")],
            [KeyboardButton(text="❌ Отменить заказ")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.full_name
    user_data[user_id] = {"name": name}
    await message.answer(f"👋 Привет, {name}! Добро пожаловать в сервис доставки.", reply_markup=start_keyboard())

@dp.message(F.text == "🛒 Новый заказ")
async def new_order(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id]["step"] = "get_products"
    await message.answer("📝 Введите список продуктов:", reply_markup=cancel_keyboard())

@dp.message(F.text == "🔙 Назад")
async def go_back(message: types.Message):
    await message.answer("⬅️ Вы вернулись назад.", reply_markup=start_keyboard())

@dp.message(F.text == "❌ Отменить заказ")
async def cancel_order(message: types.Message):
    user_data.pop(message.from_user.id, None)
    await message.answer("❌ Заказ отменён.", reply_markup=start_keyboard())

@dp.message(F.content_type == "photo")
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_data:
        photo = message.photo[-1]
        file_id = photo.file_id
        user_data[user_id]['photo'] = file_id
        await message.answer("📸 Фото получено.")
    else:
        await message.answer("📸 Фото получено, но у вас нет активного заказа.")

@dp.message()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    state = user_data.get(user_id)

    if not state or "step" not in state:
        await message.answer("❗ Нажмите «🛒 Новый заказ» для начала.")
        return

    if state["step"] == "get_products":
        state["products"] = message.text
        state["step"] = "get_address"
        await message.answer("📍 Введите адрес доставки:", reply_markup=cancel_keyboard())
        return

    if state["step"] == "get_address":
        state["address"] = message.text
        state["step"] = "confirm"
        name = state.get("name", "пользователь")
        await message.answer(
            f"🛒 Подтвердите заказ:\n\n"
            f"👤 Имя: {name}\n"
            f"📍 Адрес: {state['address']}\n"
            f"📝 Продукты:\n{state['products']}\n\n"
            f"Стоимость доставки по центру: 800₸\n"
            f"В отдалённые районы: +300₸",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Подтвердить заказ")],
                    [KeyboardButton(text="❌ Отменить заказ")]
                ],
                resize_keyboard=True
            )
        )
        return

    if state["step"] == "confirm":
        if message.text == "✅ Подтвердить заказ":
            content = state["products"]
            address = state["address"]
            photo_id = state.get("photo")

            text = (
                f"📦 Новый заказ от {state['name']} (ID: {user_id})\n\n"
                f"📍 Адрес: {address}\n"
                f"📝 Продукты:\n{content}"
            )

            if photo_id:
                await bot.send_photo(ADMIN_CHAT_ID, photo=photo_id, caption=text)
            else:
                await bot.send_message(ADMIN_CHAT_ID, text)

            await message.answer("✅ Заказ отправлен. Ожидайте подтверждения от курьера.",
                                 reply_markup=ReplyKeyboardRemove())

            user_data[user_id]['step'] = "waiting_payment"
            return

        elif message.text == "❌ Отменить заказ":
            user_data.pop(user_id, None)
            await message.answer("❌ Заказ отменён.", reply_markup=start_keyboard())
            return

    if state["step"] == "waiting_payment":
        if message.text == "💸 Оплата произведена":
            await message.answer("✅ Спасибо! Курьер уже выехал к вам.", reply_markup=start_keyboard())
            user_data.pop(user_id, None)

# ==== Webhook для Render ====

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"

async def on_startup(dispatcher):
    await bot.set_webhook(WEBHOOK_URL)

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

if __name__ == '__main__':
    web.run_app(app, host="0.0.0.0", port=int(os.getenv('PORT', 10000)))
