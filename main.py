import asyncio
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction
from openai import AsyncOpenAI
import io
from os import getenv
import base64
import re
import html
from aiogram.utils.chat_action import ChatActionSender
import logging
from openai import(
    APIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError
)

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

load_dotenv()


API_KEY=getenv("OPENROUTER_Api_Token")
TOKEN=getenv("BOT_TOKEN")
# Создаем клиента (он сам подхватит ChatGPT_API_KEY из .env или передай ключ явно)
ai_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
) 



dp=Dispatcher()
bot=Bot(token=TOKEN)

router=Router()
dp.include_router(router)


SYSTEM_PROMPT = """Ты — самостоятельный, честный и здравомыслящий собеседник. Твоя цель — помогать пользователю лучше понимать ситуацию и принимать обоснованные решения, а не просто соглашаться с ним или говорить то, что ему приятно услышать.

Основные принципы:

1. Думай независимо.
Не подстраивай выводы под ожидания пользователя, его убеждения или желаемый ответ. Не соглашайся автоматически и не поддерживай мнение лишь ради вежливости.

2. Говори правду — тактично и прямо.
Если пользователь ошибается, заблуждается или делает необоснованный вывод, спокойно скажи об этом. Объясни, в чём именно проблема, и предложи более точный взгляд или способ исправить ошибку. Не унижай, не высмеивай и не переходи на личности.

3. Отвечай трезво и взвешенно.
Отделяй факты от предположений, оценок и личных предпочтений. Учитывай контекст и возможные последствия. Не драматизируй, не преувеличивай и не делай поспешных выводов.

4. Будь честен в отношении неопределённости.
Если данных недостаточно, информация может быть устаревшей или вопрос допускает несколько трактовок — скажи об этом. Не выдумывай факты, источники, цитаты или детали. При необходимости обозначь, что именно нужно уточнить или проверить.

5. Помогай исправляться, а не просто критикуй.
Когда указываешь на ошибку, по возможности:
— кратко объясни, почему это ошибка;
— покажи, как рассуждать точнее;
— предложи конкретный следующий шаг или исправленный вариант.

Не используй служебные теги, префиксы вроде [], XML-теги и Markdown. Отвечай обычным чистым текстом.

6. Сохраняй интеллектуальную свободу и уважение.
Рассматривай идеи открыто, не навязывай пользователю взгляды и не выдавай собственные оценки за объективную истину. При этом не ставь ложное равновесие между хорошо подтверждёнными фактами и необоснованными утверждениями.

7. Отвечай по делу.
Сначала дай главный вывод, затем — необходимые пояснения. Не перегружай ответ общими фразами. Если запрос сформулирован неоднозначно, уточни его или коротко обозначь, какую трактовку ты выбрал.

Тон: спокойный, уважительный и уверенный, но не самоуверенный. Будь доброжелательным, но не угодливым. Твоя задача — не победить в споре и не польстить пользователю, а помочь ему увидеть ситуацию точнее."""



user_histories={}
def get_user_history(user_id: int):
    global user_histories
    if user_id not in user_histories:
        user_histories[user_id]=[]
    return user_histories[user_id]

def split_message(text:str, max_length: int=4000) -> list[str]:
    chunks=[]
    while len(text) > max_length:
        split_idx= text.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx=max_length
        chunks.append(text[:split_idx].strip())
        text=text[split_idx:].strip()
    if text:
        chunks.append(text)
    return chunks

def clean_markdown(text: str) -> str:
    text=re.sub(r'#{1,6}\s*(.+)', r'<b>\1</b>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    text=re.sub(r'^\-{3,}$', '───────────────', text, flags=re.MULTILINE)
    return text


@router.message(CommandStart())
async def start(message: types.Message):
    global user_histories
    await message.answer("👋 Привет! Я умный Telegram-бот на базе нейросети NVIDIA.\n\nЗадай мне любой вопрос, и я подробно отвечу!\nДоступные команды:\n\n/clear - очистить память диалога\n/help - помощь")


@router.message(Command("clear"))
async def clear(message: Message):
    global user_histories
    user_id = message.from_user.id
    if user_id in user_histories:
        user_histories[user_id].clear()
    await message.answer("🧹 Контекст беседы успешно очищен! Начнем с чистого листа.")


@router.message(Command("help"))
async def help(message: Message):
    await message.answer("💡 **Как со мной общаться:**\n\n1. Просто пиши любой текст — отвечу как нейросеть.\n2. Присылай фото с подписью — проанализирую картинку!\n3. Используй /clear если хочешь начать тему заново.")

@router.message(F.photo)
async def handl_photo(message:Message):
#    print("📸 Получено фото от пользователя!")
    await bot.send_chat_action(chat_id=message.chat.id, action= ChatAction.TYPING)
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        image_bytes = file_bytes.getvalue()
#        print(f"Размер фото: {len(image_bytes)} байт")

        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        caption=message.caption or "Что изображено на этом фото? Опиши подробно на русском языке"
#        print("Отправляю запрос в OpenRouter....")
        try:
            response = await ai_client.chat.completions.create(
            model="nvidia/nemotron-3.5-super-vl:free",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Отвечай всегда только на русском языке."
                        "Опиши изображение подробно, но без лишней воды."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                    }
            ]
        )
#            print(response.model)

            if not response.choices:
                await message.answer("Модель не смогла обработать изображение. Попробуйте другое фото.")
                return

            reply_text = response.choices[0].message.content or ""
            formatted_message=clean_markdown(reply_text)
            if not reply_text:
                await message.answer("⚠️Не удалось получить ответ от нейросети. Попробойте ещё раз позже.")
                return
       
            for chunk in split_message(formatted_message):
                    try:
                        await message.reply(chunk, parse_mode="HTML")
                    except Exception:
                        await message.reply(chunk)
                    print("Сообщение отправлено пользователю!")
        
        except RateLimitError:
            logger.warning("Превышен лимит запросов")
            await message.answer("⚠️Вы исчерпали лимит запросов. Попробуйте позже.")
            return

        except APIConnectionError:
            logger.exception("Ошибка соединения с OpenRouter")
            await message.answer("⚠️Не удалось подключиться к нейросети. Повторите попытку позже")
            return

        except APITimeoutError:
            logger.exception("Нейросеть слишком долго отвечает")
            await message.answer("⚠️Нейросеть слишком долго отвечает. Повторите ваш запрос ещё раз")
            return

        except APIStatusError as e:
            if e.status_code == 402:
                logger.warning("Недостаточно кредитов OpenRouter")
                await message.answer("⚠️ Сейчас анализ изображений недоступен! Ошибка на нашей стороне, уже чиним!\nПовторите ваш запрос немного позже!")
                return
            raise

        except APIError:
            logger.exception("Ошибка с API OpenRouter")
            await message.answer("⚠️Произошла ошибка на нашей стороне. Повторите попытку позже!")
            return

        except Exception:
            logger.exception("Непредвиденная ошибка")
            await message.answer("⚠️Произошла непредвиденная ошибка!")
            return

    except Exception as e:
        print(f"ОШИБКА В ХЭНДЛЕРЕ ФОТО: {e}")
        import traceback
        traceback.print_exc()
        await message.reply(f"⚠️ Ошибка при анализе фото: {e}")

MAX_LENGTH=3000

@router.message(F.text)
async def handl_text(message: Message):
    global user_histories
    user_id = message.from_user.id
    user_text = message.text
    if user_text == "":
            await message.reply("Вы отправили пустой запрос. Напишите вопрос текстом!")
            return
    if len(message.text)>MAX_LENGTH:
                await message.reply(
                    f"⚠️**Запрос слишком длинный!**\n\n"
                    f"Текущая длина:{len(message.text)} символов\n"
                    f"Максимально допустимая длина:{MAX_LENGTH} символов\n\n"
                    f"Пожалуйста сократите текст и отправьте снова!",
                    parse_mode="Markdown"
                )
                return
    
    async with ChatActionSender.typing(bot = bot, chat_id=message.chat.id):
        try:
            history=get_user_history(user_id)
            history.append({"role": "user", "content": user_text})
            messages_to_send = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-10:]

            print(f"Отправляю в ИИ: {messages_to_send}") # Чтобы видеть, что там не пусто

            try:
                response = await ai_client.chat.completions.create(
                    model = "nvidia/nemotron-3.5-super-vl:free",
                    messages=messages_to_send,
                    temperature = 0.7,
                    timeout=30,
            )
            except RateLimitError:
                logger.warning("Превышен лимит OpenRouter")
                await message.answer("⚠️Сейчас слишком много запросов. Попробуйте позже.")
                return 

            except APITimeoutError:
                logger.warning("OpenRouter не ответил вовремя")
                await message.answer("⚠️Нейросеть отвечает слишком долго. Попробойте ещё раз.")
                return

            except APIConnectionError:
                logger.warning("Ошибка соединения с OpenRouter")
                await message.answer("⚠️Не удалось подключиться к сервису. Проверьте соединение.")
                return

            except APIStatusError as e:
                logger.warning("Ошибка статуса API: %s", e.status_code)
                if e.status_code == 402:
                    text = "⚠️Анализ сейчас недоступен: недостаточно кредитов API."
                else:
                    text="⚠️Сервис временно недоступен!"
                await message.answer(text)
                return

            except APIError:
                logger.warning("Ошибка API OpenRouter")
                await message.answer("⚠️Сервис нейросети временно недоступен.")
                return

            except Exception:
                logger.exception("Произошла ошибка при запросе к ИИ")
                try:
                    await message.answer("⚠️Не удалось получить ответ. Попробуйте ещё раз позже.")
                except Exception:
                    logger.exception("Не удалось отправить сообщение пользователю")
                return
            
            reply_text=response.choices[0].message.content
            if not reply_text:
                logger.error("OpenRouter вернул пустой ответ: %r", response)
                await message.answer("⚠️Нейросеть не сформировала ответ. Попробуйте переформулировать вопрос.")
                return
            
            formatted_message=clean_markdown(reply_text)
            history.append({"role": "assistant", "content": formatted_message})

            for chunk in split_message(formatted_message):
                try:
                    await message.reply(chunk, parse_mode="HTML")
                except Exception:
                    await message.reply(chunk)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await message.reply(f"Ошибка:{e}")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())