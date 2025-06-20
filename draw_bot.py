import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties  
from line_generator import ImgDrawLines


TOKEN = "TOKEN"


bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
dp = Dispatcher()


TEMP_DIR = os.path.dirname(os.path.abspath(__file__))


@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("Отправь картинку чтобы получить String art картинку")


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    try:
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Getting information about the file
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Generating file names
        base_name = f"photo_{message.message_id}"
        input_path = os.path.join(TEMP_DIR, f"{base_name}.jpg")
        output_path = os.path.join(TEMP_DIR, f"{base_name}_RES.png")
        
        # Download the file
        await bot.download_file(file_path, destination=input_path)
        
        # We inform the user about the start of processing
        processing_msg = await message.answer("⏳ Обрабатываю изображение... Это может занять несколько минут")
        
        # Notifying the user about the processing process
        await bot.send_chat_action(message.chat.id, "upload_photo")
        
        # Running long processing in a separate thread
        await asyncio.to_thread(process_image, input_path, output_path)
        
        # Sending the result
        with open(output_path, 'rb') as photo_file:
            await message.answer_photo(
                types.FSInputFile(output_path),  # Using FSInputFile for large files
                caption="✅ Результат обработки"
            )
        
        # Deleting temporary files
        os.remove(input_path)
        os.remove(output_path)
        
        # Deleting the processing message
        await bot.delete_message(message.chat.id, processing_msg.message_id)
        
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при обработке: {str(e)}")
        print(f"Error: {e}")

# A function for image processing in a separate stream
def process_image(input_path: str):
    # Creating an instance and processing the image
    processor = ImgDrawLines(file_name=input_path)


# Launching the bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())