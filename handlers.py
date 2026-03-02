# handlers.py
import asyncio
from datetime import datetime, timedelta
import csv
import io
import os
import shutil
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile

import database as db
from states import *
from keyboards import *
from utils import *
from config import ADMIN_IDS, REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_LINK, TECH_ADMIN_IDS, HUNT_777_BROADCAST, BACKUP_PATH
from subscription_checker import SubscriptionChecker
from loader import bot, dp

# Глобальные переменные
bot_username = None
subscription_checker = None

# -------------------- СТАРТ И РЕГИСТРАЦИЯ --------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    db.create_user(user_id, username)
    db.update_user_activity(user_id)
    
    args = message.get_args()
    if args:
        try:
            referrer_id = int(args)
            if referrer_id == user_id:
                await show_main_menu(message)
                return
            if db.check_referral_exists(referrer_id, user_id):
                await show_main_menu(message)
                return
            captcha_data = db.get_captcha(user_id)
            if captcha_data:
                await show_main_menu(message)
                return
            referrer = db.get_user(referrer_id)
            if not referrer:
                await show_main_menu(message)
                return
            await state.update_data(referrer_id=referrer_id)
        except Exception as e:
            print(f"Ошибка при обработке реферальной ссылки: {e}")
    
    if not await check_required_channel_subscription(bot, user_id):
        required_channels = db.get_required_channels()
        if required_channels:
            channel = required_channels[0]
            _, _, channel_username, channel_link, _ = channel
            keyboard = get_required_channel_keyboard(channel_link if channel_link else f"https://t.me/{channel_username.replace('@', '')}")
            await message.answer(
                f"👋 <b>Добро пожаловать!</b>\n\n"
                f"📢 <b>Для использования бота необходимо подписаться на наш канал:</b>\n"
                f"🔗 {channel_username or channel_link}\n\n"
                f"После подписки нажмите кнопку <b>'✅ Я подписался'</b>\n\n"
                f"💡 <b>Важно:</b>\n"
                f"• Подписка обязательна для работы с ботом\n"
                f"• После подписки вы получите бонусные звезды\n"
                f"• Без подписки функционал бота недоступен",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            await RequiredChannelState.waiting_for_subscription.set()
            return
        else:
            if REQUIRED_CHANNEL_ID:
                try:
                    chat = await bot.get_chat(REQUIRED_CHANNEL_ID)
                    db.add_channel(
                        channel_id=REQUIRED_CHANNEL_ID,
                        channel_username=f"@{chat.username}" if chat.username else None,
                        channel_type='private',
                        channel_link=REQUIRED_CHANNEL_LINK or f"https://t.me/{chat.username}" if chat.username else None,
                        is_required=True
                    )
                    keyboard = get_required_channel_keyboard(REQUIRED_CHANNEL_LINK or f"https://t.me/{chat.username}" if chat.username else None)
                    await message.answer(
                        f"👋 <b>Добро пожаловать!</b>\n\n"
                        f"📢 <b>Для использования бота необходимо подписаться на наш канал:</b>\n"
                        f"🔗 {REQUIRED_CHANNEL_LINK or f'@{chat.username}' if chat.username else 'приватный канал'}\n\n"
                        f"После подписки нажмите кнопку <b>'✅ Я подписался'</b>",
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    await RequiredChannelState.waiting_for_subscription.set()
                    return
                except Exception as e:
                    print(f"Ошибка при добавлении обязательного канала: {e}")
    
    if await check_required_channel_subscription(bot, user_id):
        db.set_required_channel_subscribed(user_id, True)
        data = await state.get_data()
        referrer_id = data.get('referrer_id')
        if referrer_id:
            captcha_result = db.create_captcha(referrer_id, user_id)
            if captcha_result is None:
                db.set_registration_completed(user_id, True)
                await show_main_menu(message)
                return
            num1, num2, answer = captcha_result
            await state.update_data(referrer_id=referrer_id, captcha_answer=answer, captcha_id=db.cursor.lastrowid)
            await CaptchaState.waiting_for_captcha.set()
            keyboard = get_captcha_keyboard()
            await message.answer(
                f"🔐 <b>Капча для подтверждения реферала</b>\n\n"
                f"🎯 <b>Задание:</b> Решите простой пример\n"
                f"🧮 <b>Пример:</b> <code>{num1} + {num2} = ?</code>\n\n"
                f"📝 <b>Введите ответ:</b>\n\n"
                f"💡 <b>Информация:</b>\n"
                f"• После решения капчи вы получите 3 звезды на баланс\n"
                f"• Ваш пригласитель тоже получит 3 звезды\n"
                f"• У вас есть 3 попытки",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            db.set_registration_completed(user_id, True)
            await show_main_menu(message)
    else:
        keyboard = get_required_channel_keyboard(REQUIRED_CHANNEL_LINK)
        await message.answer(
            f"👋 <b>Добро пожаловать!</b>\n\n"
            f"📢 <b>Для использования бота необходимо подписаться на наш канал:</b>\n"
            f"🔗 {REQUIRED_CHANNEL_LINK}\n\n"
            f"После подписки нажмите кнопку <b>'✅ Я подписался'</b>",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await RequiredChannelState.waiting_for_subscription.set()

@dp.callback_query_handler(lambda c: c.data == 'check_required_channel', state=RequiredChannelState.waiting_for_subscription)
async def check_required_channel_subscription_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if await check_required_channel_subscription(bot, user_id):
        await bot.answer_callback_query(callback_query.id, "✅ Подписка подтверждена!")
        db.set_required_channel_subscribed(user_id, True)
        data = await state.get_data()
        referrer_id = data.get('referrer_id')
        if referrer_id:
            if db.check_referral_exists(referrer_id, user_id):
                db.set_registration_completed(user_id, True)
                await state.finish()
                await show_main_menu(callback_query)
                return
            captcha_result = db.create_captcha(referrer_id, user_id)
            if captcha_result is None:
                db.set_registration_completed(user_id, True)
                await state.finish()
                await show_main_menu(callback_query)
                return
            num1, num2, answer = captcha_result
            await state.update_data(referrer_id=referrer_id, captcha_answer=answer, captcha_id=db.cursor.lastrowid)
            await CaptchaState.waiting_for_captcha.set()
            keyboard = get_captcha_keyboard()
            await callback_query.message.edit_text(
                f"✅ <b>Подписка подтверждена!</b>\n\n"
                f"🔐 <b>Теперь решите капчу для получения бонуса:</b>\n"
                f"🧮 <b>Пример:</b> <code>{num1} + {num2} = ?</code>\n\n"
                f"📝 <b>Введите ответ:</b>",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            db.set_registration_completed(user_id, True)
            await state.finish()
            keyboard = get_registration_complete_keyboard()
            await callback_query.message.edit_text(
                f"🎉 <b>Регистрация завершена!</b>\n\n"
                f"✅ Вы успешно подписались на обязательный канал.\n"
                f"🚀 <b>Теперь вы можете начать зарабатывать!</b>\n\n"
                f"💰 <b>Возможности:</b>\n"
                f"• Приглашайте друзей и получайте бонусы\n"
                f"• Выполняйте задания за звезды\n"
                f"• Выводите заработанные звезды",
                parse_mode='HTML',
                reply_markup=keyboard
            )
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Вы не подписаны на канал!", show_alert=True)

@dp.message_handler(state=CaptchaState.waiting_for_captcha)
async def process_captcha(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    referrer_id = data.get('referrer_id')
    expected_answer = data.get('captcha_answer')
    captcha_id = data.get('captcha_id')
    try:
        user_answer = int(message.text.strip())
        if user_answer == expected_answer:
            if db.check_referral_exists(referrer_id, user_id):
                await message.answer(
                    f"❌ <b>Ошибка!</b>\n\n"
                    f"Вы уже зарегистрированы по реферальной ссылке.\n"
                    f"Нельзя активировать одну ссылку несколько раз.",
                    parse_mode='HTML'
                )
                await state.finish()
                await show_main_menu(message)
                return
            success = db.process_successful_captcha(referrer_id, user_id)
            if not success:
                await message.answer(
                    f"❌ <b>Ошибка!</b>\n\n"
                    f"Вы уже зарегистрированы по реферальной ссылке.",
                    parse_mode='HTML'
                )
                await state.finish()
                await show_main_menu(message)
                return
            if await check_required_channel_subscription(bot, user_id):
                db.set_required_channel_subscribed(user_id, True)
                db.give_referral_reward(referrer_id, user_id)
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🎉 Новый реферал!\n"
                        f"По вашей ссылке зарегистрировался @{message.from_user.username if message.from_user.username else 'пользователь'}!\n"
                        f"📈 На ваш баланс зачислено 3 звезды!"
                    )
                except Exception as e:
                    print(f"Не удалось отправить уведомление рефереру: {e}")
                await message.answer(
                    f"✅ <b>Капча пройдена успешно!</b>\n\n"
                    f"🎉 <b>Поздравляем!</b>\n"
                    f"💰 <b>На ваш баланс зачислено 3 звезды!</b>\n"
                    f"👥 <b>Ваш пригласитель тоже получил 3 звезды</b>\n\n"
                    f"🚀 <b>Теперь вы можете начать зарабатывать!</b>",
                    parse_mode='HTML'
                )
                await state.finish()
                await show_main_menu(message)
            else:
                await message.answer(
                    f"✅ <b>Капча пройдена успешно!</b>\n\n"
                    f"⚠️ <b>Но вы не подписаны на обязательный канал!</b>\n"
                    f"📢 Пожалуйста, подпишитесь на канал для получения бонусов.",
                    parse_mode='HTML'
                )
                await state.finish()
                await show_main_menu(message)
        else:
            db.increment_captcha_attempts(captcha_id)
            captcha_data = db.get_captcha(user_id)
            if captcha_data:
                captcha_id_db, referrer_id_db, referred_id_db, num1, num2, operation, answer, attempts, created_at = captcha_data
                if attempts >= 3:
                    db.delete_captcha(captcha_id_db)
                    await message.answer(
                        f"❌ <b>Превышено количество попыток!</b>\n\n"
                        f"⚠️ <b>К сожалению, вы не прошли капчу</b>\n"
                        f"🔄 <b>Вы можете зарегистрироваться заново без реферальной ссылки</b>\n"
                        f"💡 <b>Или попросите пригласителя отправить новую ссылку</b>",
                        parse_mode='HTML'
                    )
                    await state.finish()
                    await show_main_menu(message)
                    return
                keyboard = get_captcha_keyboard()
                await message.answer(
                    f"❌ <b>Неправильный ответ!</b>\n\n"
                    f"🎯 <b>Попробуйте еще раз:</b>\n"
                    f"🧮 <b>Пример:</b> <code>{num1} + {num2} = ?</code>\n\n"
                    f"📊 <b>Попыток использовано:</b> {attempts}/3\n"
                    f"📝 <b>Введите ответ:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
    except ValueError:
        await message.answer(
            "❌ <b>Некорректный ввод!</b>\n\n"
            "📝 <b>Пожалуйста, введите число</b>\n"
            "💡 <b>Пример ответа:</b> <code>25</code>",
            parse_mode='HTML'
        )

@dp.callback_query_handler(lambda c: c.data == 'skip_captcha', state=CaptchaState.waiting_for_captcha)
async def skip_captcha(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    captcha_data = db.get_captcha(user_id)
    if captcha_data:
        captcha_id = captcha_data[0]
        db.delete_captcha(captcha_id)
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer(
        "⏭️ <b>Капча пропущена</b>\n\n"
        "🚀 <b>Вы можете начать пользоваться ботом</b>\n"
        "💡 <b>Но бонусы за реферала не будут начислены</b>",
        parse_mode='HTML'
    )
    await state.finish()
    db.set_registration_completed(user_id, True)
    await show_main_menu(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == 'start_earning')
async def start_earning(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await show_main_menu(callback_query)

async def show_main_menu(message_or_call):
    if isinstance(message_or_call, types.Message):
        message = message_or_call
    else:
        message = message_or_call.message
    user_id = message.chat.id
    balance = db.get_balance(user_id)
    db.update_user_activity(user_id)
    keyboard = get_main_menu_keyboard()
    text = (
        f"✨ <b>Добро пожаловать в STILNI BOT!</b> ✨\n\n"
        f"🪙 <b>Ваш баланс:</b> <code>{balance} звезд</code>\n\n"
        f"🚀 <b>Зарабатывай звезды:</b>\n"
        f"• Приглашай друзей - <b>3 звезды</b> за каждого\n"
        f"• Выполняй задания - <b>2 звезды</b> за подписку\n"
        f"• Активируй промокоды\n\n"
        f"🎯 <b>Выбирай действие:</b>"
    )
    if isinstance(message_or_call, types.Message):
        await message.answer(text, parse_mode='HTML', reply_markup=keyboard)
    else:
        await message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

# -------------------- ОСНОВНЫЕ РАЗДЕЛЫ МЕНЮ --------------------
@dp.callback_query_handler(lambda c: c.data == 'earn')
async def process_earn(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    global bot_username
    if not bot_username:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned = user_data[1] if user_data else 0
    keyboard = get_back_to_menu_keyboard()
    text = (
        f"💰 <b>Заработок звезд</b>\n\n"
        f"📊 <b>Ваша реферальная статистика:</b>\n"
        f"• Приглашено друзей: <code>{referrals}</code>\n"
        f"• Заработано с рефералов: <code>{earned} звезд</code>\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💡 <b>Как работает:</b>\n"
        f"1. Отправь друзьям ссылку выше\n"
        f"2. За каждого друга получишь <b>3 звезды</b>\n"
        f"3. Твой друг тоже получит бонус!"
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'tasks')
async def process_tasks(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_registration_completed(user_id):
        await bot.answer_callback_query(callback_query.id, "❌ Сначала завершите регистрацию! Подпишитесь на обязательный канал.", show_alert=True)
        return
    channels = db.get_channels()
    if not channels:
        keyboard = get_back_to_menu_keyboard()
        await bot.answer_callback_query(callback_query.id, "На данный момент заданий нет", show_alert=True)
        await callback_query.message.edit_text(
            "📭 <b>Задания</b>\n\n"
            "😔 К сожалению, сейчас нет доступных заданий.\n"
            "Загляни позже - администратор добавит новые задания!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return
    completed_tasks = db.get_user_completed_tasks(user_id)
    completed_channels = [task[0] for task in completed_tasks]
    keyboard = get_tasks_keyboard(user_id, channels, completed_channels)
    text = (
        f"📋 <b>Доступные задания</b>\n\n"
        f"🎯 <b>Что нужно сделать:</b>\n"
        f"1. Подпишись на каналы ниже\n"
        f"2. Нажми кнопку <b>'Проверить подписки'</b>\n"
        f"3. Получи <b>2 звезды</b> за каждую подписку!\n\n"
        f"💰 <b>Награда:</b> 2 звезды за канал\n"
        f"📈 <b>Всего заданий:</b> {len(channels)}\n"
        f"✅ <b>Выполнено:</b> {len(completed_tasks)}/{len(channels)}\n"
        f"💡 <b>Совет:</b> Подпишись на все каналы для максимальной награды!"
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'check_subs')
async def check_subscriptions(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_registration_completed(user_id):
        await bot.answer_callback_query(callback_query.id, "❌ Сначала завершите регистрацию! Подпишитесь на обязательный канал.", show_alert=True)
        return
    channels = db.get_channels()
    deducted = await check_all_subscriptions(bot, user_id)
    if deducted > 0:
        await callback_query.message.answer(
            f"⚠️ <b>Внимание!</b>\n\n"
            f"Вы отписались от каналов, за которые получали награду.\n"
            f"С вашего баланса списано <b>{deducted} звёзд</b>.",
            parse_mode='HTML'
        )
    awarded = 0
    newly_completed = 0
    already_completed = 0
    total_tasks = len(channels)
    for channel in channels:
        channel_db_id, channel_id, channel_username, channel_link, channel_type, is_required, deadline, max_subscribers, current_subscribers = channel
        if is_required:
            continue
        completed, stars_awarded = db.check_task_completion(user_id, channel_db_id)
        if completed:
            already_completed += 1
            continue
        try:
            chat_identifier = channel_id if channel_type == 'private' else channel_username
            if channel_type == 'private' and not channel_link:
                continue
            chat_member = await bot.get_chat_member(chat_id=chat_identifier, user_id=user_id)
            if chat_member.status in ['member', 'administrator', 'creator']:
                db.complete_task(user_id, channel_db_id, 2)
                db.update_balance(user_id, 2, f"Награда за подписку на {channel_username}")
                awarded += 2
                newly_completed += 1
                await bot.send_message(
                    user_id,
                    f"✅ <b>Задание выполнено!</b>\n\n"
                    f"📢 <b>Канал:</b> {channel_username if channel_username else 'Приватный канал'}\n"
                    f"💰 <b>Начислено:</b> 2 звезды\n"
                    f"💎 <b>Баланс:</b> {db.get_balance(user_id)} звезд",
                    parse_mode='HTML'
                )
        except Exception as e:
            print(f"Ошибка при проверке канала {channel_username or channel_id}: {e}")
            continue
    keyboard = get_back_to_menu_keyboard()
    if newly_completed > 0:
        text = (
            f"✅ <b>Проверка завершена!</b>\n\n"
            f"🎉 <b>Отличная работа!</b>\n"
            f"• Уже выполнено ранее: <code>{already_completed}</code>\n"
            f"• Новых выполненных: <code>{newly_completed}</code>\n"
            f"• Всего заданий: <code>{total_tasks}</code>\n"
            f"• Начислено звезд: <code>{awarded}</code>\n"
            f"• Новый баланс: <code>{db.get_balance(user_id)}</code>\n\n"
            f"💰 <b>Продолжай в том же духе!</b>\n"
            f"Чем больше заданий выполнишь - тем больше заработаешь!"
        )
    else:
        text = (
            f"📋 <b>Проверка подписок</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Уже выполнено: <code>{already_completed}/{total_tasks}</code>\n"
            f"• Новых выполнено: <code>{newly_completed}</code>\n"
            f"• Начислено звезд: <code>{awarded}</code>\n\n"
        )
        if already_completed == total_tasks:
            text += (
                f"🎉 <b>Вы выполнили все задания!</b>\n"
                f"✅ <b>Статус:</b> Все задания завершены\n\n"
                f"💡 <b>Ждите новые задания от администратора</b>"
            )
        else:
            text += (
                f"💡 <b>Что делать:</b>\n"
                f"1. Убедись, что подписался на все каналы\n"
                f"2. Если подписался - подожди пару минут\n"
                f"3. Попробуй проверить снова\n\n"
                f"🔄 <b>Проверь подписки и возвращайся!</b>"
            )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'task_completed')
async def task_already_completed(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id, "✅ Вы уже выполнили это задание!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == 'withdraw')
async def process_withdraw(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_registration_completed(user_id):
        await bot.answer_callback_query(callback_query.id, "❌ Сначала завершите регистрацию! Подпишитесь на обязательный канал.", show_alert=True)
        return
    balance = db.get_balance(user_id)
    keyboard = get_withdrawal_keyboard()
    text = (
        f"💳 <b>Вывод звезд</b>\n\n"
        f"💰 <b>Доступно для вывода:</b> <code>{balance} звезд</code>\n\n"
        f"🎯 <b>Выбери сумму:</b>\n"
        f"• 15 звёзд - минимальный вывод\n"
        f"• 100 звёзд - максимальный за раз\n\n"
        f"📝 <b>Как это работает:</b>\n"
        f"1. Выбери сумму вывода\n"
        f"2. Укажи @username для получения\n"
        f"3. Ожидай обработки заявки\n"
        f"4. Получай выплату!\n\n"
        f"⏰ <b>Время обработки:</b> до 24 часов"
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('withdraw_'))
async def process_withdraw_amount(callback_query: types.CallbackQuery, state: FSMContext):
    amount = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    balance = db.get_balance(user_id)
    if balance < amount:
        await bot.answer_callback_query(callback_query.id, f"❌ Недостаточно звезд. Ваш баланс: {balance}", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    await state.update_data(amount=amount)
    await WithdrawalState.waiting_for_username.set()
    keyboard = get_back_to_menu_keyboard()
    await callback_query.message.edit_text(
        f"💳 <b>Вывод {amount} звезд</b>\n\n"
        f"📝 <b>Введите ваш @username в Telegram:</b>\n\n"
        f"💡 <b>Важно:</b>\n"
        f"• Укажите действующий @username\n"
        f"• Убедитесь, что у вас открытый профиль\n"
        f"• Вывод осуществляется только на @username\n\n"
        f"❌ <b>Не принимаются:</b>\n"
        f"• Номера телефонов\n"
        f"• Ссылки на каналы\n"
        f"• Другие идентификаторы",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'custom_withdraw')
async def custom_withdraw(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    balance = db.get_balance(user_id)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="withdraw"))
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        f"🏦 <b>Другая сумма</b>\n\n"
        f"💰 <b>Доступно:</b> <code>{balance} звезд</code>\n\n"
        f"📝 <b>Как вывести другую сумма:</b>\n"
        f"1. Отправьте сообщение в формате:\n"
        f"<code>/withdraw [сумма] [@username]</code>\n\n"
        f"💡 <b>Пример:</b>\n"
        f"<code>/withdraw 75 @ваш_username</code>\n\n"
        f"⚠️ <b>Условия:</b>\n"
        f"• Минимальная сумма: 15 звезд\n"
        f"• Максимальная сумма: ваш баланс\n"
        f"• Только действующий @username",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.message_handler(commands=['withdraw'])
async def cmd_withdraw(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    if not db.is_registration_completed(user_id):
        await message.answer(
            "❌ <b>Сначала завершите регистрацию!</b>\n\n"
            "📢 Для использования бота необходимо подписаться на обязательный канал.",
            parse_mode='HTML'
        )
        return
    if len(args) != 3:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "📝 <b>Используйте:</b>\n"
            "<code>/withdraw [сумма] [@username]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/withdraw 50 @username</code>",
            parse_mode='HTML'
        )
        return
    try:
        amount = int(args[1])
        username = args[2]
        if not username.startswith('@'):
            username = '@' + username
        balance = db.get_balance(user_id)
        if amount < 15:
            await message.answer("❌ Минимальная сумма вывода - 15 звезд")
            return
        if amount > balance:
            await message.answer(f"❌ Недостаточно звезд. Ваш баланс: {balance}")
            return
        db.update_balance(user_id, -amount, f"Вывод средств на {username}")
        withdrawal_id = db.add_withdrawal(user_id, amount, username)
        admin_keyboard = get_admin_withdrawal_keyboard(withdrawal_id)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📋 <b>НОВАЯ ЗАЯВКА НА ВЫВОД #{withdrawal_id}</b>\n\n"
                    f"💰 <b>Сумма:</b> {amount} звезд\n"
                    f"👤 <b>Получатель:</b> {username}\n"
                    f"👥 <b>User ID:</b> {user_id}\n"
                    f"⏰ <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"📊 <b>Статус:</b> ⏳ Ожидает подтверждения",
                    parse_mode='HTML',
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                print(f"Не удалось отправить заявку администратору {admin_id}: {e}")
        await message.answer(
            f"✅ <b>Заявка создана!</b>\n\n"
            f"💰 <b>Сумма:</b> {amount} звезд\n"
            f"👤 <b>Получатель:</b> {username}\n"
            f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n\n"
            f"⏳ <b>Статус:</b> Ожидает обработки\n"
            f"📞 <b>Связь:</b> @{bot_username}",
            parse_mode='HTML'
        )
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")

@dp.message_handler(state=WithdrawalState.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    amount = data['amount']
    if not username.startswith('@'):
        username = '@' + username
    balance = db.get_balance(user_id)
    if balance < amount:
        await message.answer(f"❌ Недостаточно звезд. Ваш баланс: {balance}")
        await state.finish()
        await show_main_menu(message)
        return
    db.update_balance(user_id, -amount, f"Вывод средств на {username}")
    withdrawal_id = db.add_withdrawal(user_id, amount, username)
    admin_keyboard = get_admin_withdrawal_keyboard(withdrawal_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📋 <b>НОВАЯ ЗАЯВКА НА ВЫВОД #{withdrawal_id}</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"👥 <b>User ID:</b> {user_id}\n"
                f"⏰ <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📊 <b>Статус:</b> ⏳ Ожидает подтверждения",
                parse_mode='HTML',
                reply_markup=admin_keyboard
            )
        except Exception as e:
            print(f"Не удалось отправить заявку администратору {admin_id}: {e}")
    await message.answer(
        f"✅ <b>Заявка создана!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount} звёзд\n"
        f"👤 <b>Получатель:</b> {username}\n"
        f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n\n"
        f"⏳ <b>Статус:</b> Ожидает обработки\n"
        f"📞 <b>Связь:</b> @{bot_username}",
        parse_mode='HTML'
    )
    await state.finish()
    await show_main_menu(message)

@dp.callback_query_handler(lambda c: c.data == 'profile')
async def process_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    balance = db.get_balance(user_id)
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned_refs = user_data[1] if user_data else 0
    completed_tasks = len(db.get_user_completed_tasks(user_id))
    text = get_user_info_text(user_id, callback_query.from_user.username, balance, referrals, earned_refs, completed_tasks)
    keyboard = get_profile_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'my_stats')
async def my_stats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    balance = db.get_balance(user_id)
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned_refs = user_data[1] if user_data else 0
    completed_tasks = len(db.get_user_completed_tasks(user_id))
    cursor.execute('SELECT COUNT(*) FROM promo_activations WHERE user_id = ?', (user_id,))
    activated_promos = cursor.fetchone()[0]
    total_earned = earned_refs + (completed_tasks * 2) + balance
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="profile"))
    text = (
        f"📊 <b>Моя статистика</b>\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• Текущий баланс: <code>{balance} звезд</code>\n"
        f"• Всего заработано: <code>{total_earned} звезд</code>\n"
        f"• Заработано с рефералов: <code>{earned_refs} звезд</code>\n\n"
        f"🎯 <b>Активность:</b>\n"
        f"• Приглашено друзей: <code>{referrals}</code>\n"
        f"• Выполнено заданий: <code>{completed_tasks}</code>\n"
        f"• Активировано промокодов: <code>{activated_promos}</code>\n\n"
        f"🏆 <b>Рейтинг:</b>\n"
        f"• Реферальный ранг: <code>#{referrals + 1}</code>\n"
        f"• Активность: <code>Высокая</code>\n\n"
        f"🚀 <b>Продолжай в том же духе!</b>"
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'activate_promo')
async def activate_promo_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await PromoState.waiting_for_promo.set()
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data="profile"))
    await callback_query.message.edit_text(
        f"🎁 <b>Активация промокода</b>\n\n"
        f"✨ <b>Введите промокод:</b>\n\n"
        f"💡 <b>Как получить промокод:</b>\n"
        f"• Следите за новостями бота\n"
        f"• Участвуйте в конкурсах\n"
        f"• Специальные акции\n\n"
        f"🎯 <b>Пример промокода:</b> <code>WELCOME2024</code>\n\n"
        f"⚠️ <b>Внимание:</b>\n"
        f"• Промокод активируется один раз\n"
        f"• Учитывайте регистр букв\n"
        f"• Срок действия ограничен",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.message_handler(state=PromoState.waiting_for_promo)
async def process_promo(message: types.Message, state: FSMContext):
    promo_code = message.text.strip()
    user_id = message.from_user.id
    if not db.is_registration_completed(user_id):
        await message.answer(
            "❌ <b>Сначала завершите регистрацию!</b>\n\n"
            "📢 Для использования бота необходимо подписаться на обязательный канал.",
            parse_mode='HTML'
        )
        await state.finish()
        return
    promo = db.get_promo(promo_code)
    if not promo:
        await message.answer(
            "❌ <b>Промокод не найден</b>\n\n"
            "💡 <b>Возможные причины:</b>\n"
            "• Промокод введен неверно\n"
            "• Промокод закончился\n"
            "• Промокод еще не активирован\n\n"
            "🔄 <b>Попробуйте еще раз</b>",
            parse_mode='HTML'
        )
        await state.finish()
        await show_main_menu(message)
        return
    promo_id = promo[0]
    success, result_message = db.activate_promo(user_id, promo_id)
    if success:
        stars = promo[2]
        await message.answer(
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"✅ <b>Промокод активирован</b>\n"
            f"🎁 <b>Получено:</b> {stars} звезд\n"
            f"💰 <b>Новый баланс:</b> {db.get_balance(user_id)} звезд\n\n"
            f"✨ <b>Спасибо за активность!</b>",
            parse_mode='HTML'
        )
    else:
        await message.answer(
            f"❌ <b>Не удалось активировать</b>\n\n"
            f"{result_message}\n\n"
            f"🔄 <b>Попробуйте другой промокод</b>",
            parse_mode='HTML'
        )
    await state.finish()
    await show_main_menu(message)

@dp.callback_query_handler(lambda c: c.data == 'top_ref')
async def top_referrers(callback_query: types.CallbackQuery):
    top_users = db.get_top_referrers(15)
    if not top_users:
        text = "🏆 <b>Топ рефералов</b>\n\n😔 Пока никто не пригласил друзей...\n\n🚀 Стань первым в топе!"
    else:
        text = "🏆 <b>ТОП-15 Рефералов</b>\n\n"
        for idx, (user_id, username, referrals, earned) in enumerate(top_users, 1):
            username_display = f"@{username}" if username else f"ID: {user_id}"
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            text += f"{medal} {username_display}\n   👥 {referrals} друзей | 💰 {earned} звезд\n\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'stats_user')
async def user_stats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned_refs = user_data[1] if user_data else 0
    stats = db.get_user_stats()
    cursor.execute('SELECT COUNT(*) + 1 FROM users WHERE referrals > (SELECT referrals FROM users WHERE user_id = ?)', (user_id,))
    top_position = cursor.fetchone()[0]
    text = (
        f"📊 <b>Общая статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего пользователей: <code>{stats['total_users']}</code>\n"
        f"• Ваша позиция в топе: <code>#{top_position}</code>\n\n"
        f"💰 <b>Экономика:</b>\n"
        f"• Всего звезд в системе: <code>{stats['total_stars']}</code>\n"
        f"• Всего каналов: <code>{stats['total_channels']}</code>\n\n"
        f"🎯 <b>Ваши показатели:</b>\n"
        f"• Приглашено друзей: <code>{referrals}</code>\n"
        f"• Заработано с рефералов: <code>{earned_refs} звезд</code>\n\n"
        f"🚀 <b>Цель:</b> Попасть в ТОП-3 рефералов!"
    )
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏆 Топ рефералов", callback_data="top_ref"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_menu"))
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'back_menu')
async def back_to_menu(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await show_main_menu(callback_query)

# -------------------- ОБРАБОТКА ЗАЯВОК НА ВЫВОД (ДЛЯ АДМИНОВ) --------------------
@dp.callback_query_handler(lambda c: c.data.startswith(('confirm_', 'pay_', 'reject_')))
async def process_withdrawal_action(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут обрабатывать заявки", show_alert=True)
        return
    action, withdrawal_id_str = callback_query.data.split('_')
    withdrawal_id = int(withdrawal_id_str)
    withdrawal = db.get_withdrawal(withdrawal_id)
    if not withdrawal:
        await bot.answer_callback_query(callback_query.id, "Заявка не найдена", show_alert=True)
        return
    withdrawal_id_db, user_id, amount, username, status, created_at = withdrawal
    admin_username = callback_query.from_user.username or "Админ"
    if action == 'confirm':
        if status == 'pending':
            db.update_withdrawal_status(withdrawal_id, 'confirmed')
            await bot.send_message(
                user_id,
                f"✅ <b>Заявка подтверждена!</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n\n"
                f"📊 <b>Статус:</b> Ожидает оплаты\n"
                f"⏰ <b>Время подтверждения:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"💸 <b>Оплата будет произведена в течение 24 часов</b>",
                parse_mode='HTML'
            )
            admin_keyboard = InlineKeyboardMarkup(row_width=3)
            admin_keyboard.add(
                InlineKeyboardButton("✅ Подтверждено", callback_data=f"noaction_{withdrawal_id}"),
                InlineKeyboardButton("💰 Оплатить", callback_data=f"pay_{withdrawal_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{withdrawal_id}")
            )
            await bot.edit_message_text(
                f"📋 <b>ЗАЯВКА НА ВЫВОД #{withdrawal_id}</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"👥 <b>User ID:</b> {user_id}\n"
                f"⏰ <b>Время создания:</b> {created_at}\n"
                f"✅ <b>Подтвердил:</b> @{admin_username}\n"
                f"🕐 <b>Время подтверждения:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"📊 <b>Статус:</b> ✅ ПОДТВЕРЖДЕНО",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                parse_mode='HTML',
                reply_markup=admin_keyboard
            )
            await bot.answer_callback_query(callback_query.id, "✅ Заявка подтверждена")
        else:
            await bot.answer_callback_query(callback_query.id, f"⚠️ Заявка уже имеет статус: {status}", show_alert=True)
    elif action == 'pay':
        if status == 'confirmed' or status == 'pending':
            db.update_withdrawal_status(withdrawal_id, 'paid')
            await bot.send_message(
                user_id,
                f"🎉 <b>Заявка оплачена!</b>\n\n"
                f"✅ <b>Статус:</b> ВЫПЛАЧЕНО\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n"
                f"👨‍💼 <b>Оплатил:</b> @{admin_username}\n"
                f"⏰ <b>Время оплаты:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"💸 <b>Средства отправлены!</b>\n"
                f"Спасибо, что пользуетесь нашим ботом! 🚀",
                parse_mode='HTML'
            )
            admin_keyboard = InlineKeyboardMarkup(row_width=3)
            admin_keyboard.add(
                InlineKeyboardButton("✅ Подтверждено", callback_data=f"noaction_{withdrawal_id}"),
                InlineKeyboardButton("💰 Оплачено", callback_data=f"noaction_{withdrawal_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"noaction_{withdrawal_id}")
            )
            await bot.edit_message_text(
                f"📋 <b>ЗАЯВКА НА ВЫВОД #{withdrawal_id} - ОПЛАЧЕНА</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"👥 <b>User ID:</b> {user_id}\n"
                f"⏰ <b>Время создания:</b> {created_at}\n"
                f"👨‍💼 <b>Оплатил:</b> @{admin_username}\n"
                f"🕐 <b>Время оплаты:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"📊 <b>Статус:</b> 💰 ОПЛАЧЕНО",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                parse_mode='HTML',
                reply_markup=admin_keyboard
            )
            await bot.answer_callback_query(callback_query.id, "💰 Заявка оплачена")
        elif status == 'paid':
            await bot.answer_callback_query(callback_query.id, "⚠️ Заявка уже оплачена", show_alert=True)
        else:
            await bot.answer_callback_query(callback_query.id, f"❌ Нельзя оплатить заявку со статусом: {status}", show_alert=True)
    elif action == 'reject':
        if status != 'rejected':
            db.update_withdrawal_status(withdrawal_id, 'rejected')
            db.update_balance(user_id, amount, f"Возврат средств по заявке #{withdrawal_id}")
            await bot.send_message(
                user_id,
                f"❌ <b>Заявка отклонена</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"🆔 <b>Номер заявки:</b> {withdrawal_id}\n"
                f"👨‍💼 <b>Отклонил:</b> @{admin_username}\n\n"
                f"💡 <b>Причина:</b> Неверные данные\n"
                f"🔄 <b>Статус:</b> Звезды возвращены на баланс\n"
                f"💰 <b>Текущий баланс:</b> {db.get_balance(user_id)} звезд\n\n"
                f"📞 <b>По вопросам:</b> @{bot_username}",
                parse_mode='HTML'
            )
            admin_keyboard = InlineKeyboardMarkup(row_width=3)
            admin_keyboard.add(
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"noaction_{withdrawal_id}"),
                InlineKeyboardButton("💰 Оплатить", callback_data=f"noaction_{withdrawal_id}"),
                InlineKeyboardButton("❌ Отклонено", callback_data=f"noaction_{withdrawal_id}")
            )
            await bot.edit_message_text(
                f"📋 <b>ЗАЯВКА НА ВЫВОД #{withdrawal_id} - ОТКЛОНЕНА</b>\n\n"
                f"💰 <b>Сумма:</b> {amount} звезд\n"
                f"👤 <b>Получатель:</b> {username}\n"
                f"👥 <b>User ID:</b> {user_id}\n"
                f"⏰ <b>Время создания:</b> {created_at}\n"
                f"👨‍💼 <b>Отклонил:</b> @{admin_username}\n"
                f"🕐 <b>Время отклонения:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"📊 <b>Статус:</b> ❌ ОТКЛОНЕНО\n"
                f"💰 <b>Действие:</b> Звезды возвращены пользователю",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                parse_mode='HTML',
                reply_markup=admin_keyboard
            )
            await bot.answer_callback_query(callback_query.id, "❌ Заявка отклонена")
        else:
            await bot.answer_callback_query(callback_query.id, "⚠️ Заявка уже отклонена", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('noaction_'))
async def no_action(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id, "Это действие уже выполнено", show_alert=True)

# -------------------- КОМАНДА /CHECKBALANCE И ПРОСМОТР РЕФЕРАЛОВ --------------------
@dp.message_handler(commands=['checkbalance'])
async def cmd_checkbalance(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "👤 <b>Проверка баланса пользователя</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/checkbalance @username</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/checkbalance @username</code>\n\n"
            "📊 <b>Можно также по ID:</b>\n"
            "<code>/checkbalance 1234567890</code>",
            parse_mode='HTML'
        )
        return
    identifier = args[1].replace('@', '')
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except ValueError:
        user = db.get_user_by_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    user_id = user[0]
    username = user[1] if len(user) > 1 else identifier
    balance = user[2] if len(user) > 2 else db.get_balance(user_id)
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned_refs = user_data[1] if user_data else 0
    keyboard = InlineKeyboardMarkup(row_width=1)
    if referrals > 0:
        keyboard.add(InlineKeyboardButton("👥 Посмотреть рефералов", callback_data=f"view_referrals_{user_id}"))
    await message.answer(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Username:</b> @{username}\n"
        f"💰 <b>Баланс:</b> <code>{balance} звезд</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Приглашено друзей: <code>{referrals}</code>\n"
        f"• Заработано с рефералов: <code>{earned_refs} звезд</code>\n\n"
        f"⏰ <b>Время проверки:</b> {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('view_referrals_'))
async def view_user_referrals(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут просматривать эту информацию", show_alert=True)
        return
    user_id = int(callback_query.data.split('_')[2])
    user = db.get_user(user_id)
    if not user:
        await bot.answer_callback_query(callback_query.id, "❌ Пользователь не найден", show_alert=True)
        return
    username = user[1] if len(user) > 1 else f"ID: {user_id}"
    referrals = db.get_referrals_by_user(user_id)
    if not referrals:
        await bot.answer_callback_query(callback_query.id, "❌ У этого пользователя нет рефералов", show_alert=True)
        return
    text = f"👥 <b>Список рефералов пользователя @{username}</b>\n\n"
    for idx, (referred_id, referred_username, activated_at) in enumerate(referrals, 1):
        username_display = f"@{referred_username}" if referred_username else f"ID: {referred_id}"
        try:
            date_obj = datetime.strptime(activated_at, '%Y-%m-%d %H:%M:%S')
            date_str = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = str(activated_at)
        text += f"{idx}. {username_display}\n"
        text += f"   🆔 ID: <code>{referred_id}</code>\n"
        text += f"   📅 Зарегистрирован: {date_str}\n\n"
    text += f"\n📊 <b>Всего рефералов:</b> {len(referrals)}"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад к информации", callback_data=f"back_to_info_{user_id}"))
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('back_to_info_'))
async def back_to_user_info(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Только администраторы могут использовать эту функцию", show_alert=True)
        return
    user_id = int(callback_query.data.split('_')[3])
    user = db.get_user(user_id)
    if not user:
        await bot.answer_callback_query(callback_query.id, "❌ Пользователь не найден", show_alert=True)
        return
    username = user[1] if len(user) > 1 else f"ID: {user_id}"
    balance = db.get_balance(user_id)
    cursor = db.conn.cursor()
    cursor.execute('SELECT referrals, earned_from_refs FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    referrals = user_data[0] if user_data else 0
    earned_refs = user_data[1] if user_data else 0
    keyboard = InlineKeyboardMarkup(row_width=1)
    if referrals > 0:
        keyboard.add(InlineKeyboardButton("👥 Посмотреть рефералов", callback_data=f"view_referrals_{user_id}"))
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=(
                f"👤 <b>Информация о пользователе</b>\n\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"👤 <b>Username:</b> @{username}\n"
                f"💰 <b>Баланс:</b> <code>{balance} звезд</code>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Приглашено друзей: <code>{referrals}</code>\n"
                f"• Заработано с рефералов: <code>{earned_refs} звезд</code>\n\n"
                f"⏰ <b>Время проверки:</b> {datetime.now().strftime('%H:%M:%S')}"
            ),
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await bot.answer_callback_query(callback_query.id)
    except Exception as e:
        await bot.answer_callback_query(callback_query.id, f"❌ Ошибка: {str(e)}", show_alert=True)

# -------------------- НОВЫЕ РАЗДЕЛЫ: РЕФЕРАЛКА, КАЗИНО, РЕЙТИНГ, ИСТОРИЯ --------------------
@dp.callback_query_handler(lambda c: c.data == 'referral_system')
async def referral_system(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_registration_completed(user_id):
        await bot.answer_callback_query(callback_query.id, "❌ Сначала завершите регистрацию!", show_alert=True)
        return
    keyboard = get_referral_system_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "👥 <b>Реферальная система</b>\n\n"
        "Приглашайте друзей и получайте бонусы!",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'get_ref_link')
async def get_ref_link(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    global bot_username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await bot.send_message(
        user_id,
        f"🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"📋 Нажмите на ссылку выше, чтобы скопировать.",
        parse_mode='HTML'
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == 'my_referrals')
async def my_referrals(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    referrals = db.get_referrals_by_user(user_id)
    if not referrals:
        text = "👥 У вас пока нет рефералов. Пригласите друзей!"
    else:
        text = "👥 <b>Ваши рефералы:</b>\n\n"
        for idx, (ref_id, username, date) in enumerate(referrals, 1):
            username_display = f"@{username}" if username else f"ID: {ref_id}"
            date_str = date.split()[0] if date else "неизвестно"
            text += f"{idx}. {username_display} (с {date_str})\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'casino')
async def casino_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_registration_completed(user_id):
        await bot.answer_callback_query(callback_query.id, "❌ Сначала завершите регистрацию!", show_alert=True)
        return
    balance = db.get_balance(user_id)
    keyboard = get_casino_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        f"🎰 <b>Казино</b>\n\n"
        f"💰 Ваш баланс: <code>{balance} ⭐</code>\n\n"
        f"🎲 <b>Правила:</b>\n"
        f"• Выберите ставку\n"
        f"• Бот кинет игральный автомат (🎰)\n"
        f"• Выигрыш: три семерки (777) = x3\n"
        f"• Во время ивента множитель может быть x5!\n"
        f"• При проигрыше ставка сгорает\n\n"
        f"🎯 <b>Выберите ставку:</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('casino_'))
async def casino_play(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    bet = int(callback_query.data.split('_')[1])
    balance = db.get_balance(user_id)
    if balance < bet:
        await bot.answer_callback_query(callback_query.id, f"❌ Недостаточно средств. Ваш баланс: {balance} ⭐", show_alert=True)
        return
    event = db.get_active_event('casino')
    multiplier = event[3] if event else 3
    msg = await bot.send_dice(user_id, emoji='🎰')
    await asyncio.sleep(3)
    value = msg.dice.value
    win = 0
    result_text = ""
    if value == 64:
        win = bet * multiplier
        result_text = f"🎉 <b>ДЖЕКПОТ! 777!</b> x{multiplier}\n"
        result_text += f"💰 Вы выиграли <b>{win} ⭐</b>!"
        if HUNT_777_BROADCAST and db.get_user(user_id):
            username = callback_query.from_user.username or f"id{user_id}"
            await bot.send_message(
                user_id,
                f"🎉 @{username} поймал 777 в казино! Поздравляем!"
            )
    else:
        if 60 <= value <= 63:
            result_text = f"😱 <b>Почти!</b> До 777 совсем немного... (выпало {value})\n"
        else:
            result_text = f"❌ Выпало {value}. Повезет в следующий раз!\n"
        win = 0
    db.update_balance(user_id, -bet, f"Ставка в казино")
    if win > 0:
        db.update_balance(user_id, win, f"Выигрыш в казино (x{multiplier})")
    db.add_casino_game(user_id, bet, value, win, multiplier)
    new_balance = db.get_balance(user_id)
    result_text += f"\n\n💰 Текущий баланс: <code>{new_balance} ⭐</code>"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎰 Играть еще", callback_data="casino"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(result_text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'rating_menu')
async def rating_menu(callback_query: types.CallbackQuery):
    keyboard = get_rating_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "🏆 <b>Рейтинги</b>\n\n"
        "Выберите категорию:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'rating_ref')
async def rating_ref(callback_query: types.CallbackQuery):
    top = db.get_top_by_referrals(15)
    text = "🏆 <b>Топ по рефералам</b>\n\n"
    if not top:
        text += "😔 Пока никого нет."
    else:
        for idx, (user_id, username, referrals) in enumerate(top, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            username_display = f"@{username}" if username else f"ID: {user_id}"
            text += f"{medal} {username_display} — {referrals} реф.\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'rating_balance')
async def rating_balance(callback_query: types.CallbackQuery):
    top = db.get_top_by_balance(15)
    text = "🏆 <b>Топ по балансу</b>\n\n"
    if not top:
        text += "😔 Пока никого нет."
    else:
        for idx, (user_id, username, balance) in enumerate(top, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            username_display = f"@{username}" if username else f"ID: {user_id}"
            text += f"{medal} {username_display} — {balance} ⭐\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'rating_casino')
async def rating_casino(callback_query: types.CallbackQuery):
    top = db.get_top_by_casino_wins(15)
    text = "🏆 <b>Топ по выигрышам в казино</b>\n\n"
    if not top:
        text += "😔 Пока никого нет."
    else:
        for idx, (user_id, username, wins) in enumerate(top, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            username_display = f"@{username}" if username else f"ID: {user_id}"
            text += f"{medal} {username_display} — {wins} ⭐\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'user_history')
async def user_history(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    history = db.get_user_full_history(user_id)
    text = f"📜 <b>История пользователя @{callback_query.from_user.username or user_id}</b>\n\n"
    text += "💰 <b>Последние транзакции:</b>\n"
    if history['transactions']:
        for t in history['transactions'][:5]:
            amount, ttype, desc, date = t
            sign = "+" if amount > 0 else ""
            date_str = date.split()[0] if date else ""
            text += f"{sign}{amount} ⭐ — {desc} ({date_str})\n"
    else:
        text += "Нет транзакций\n"
    text += "\n👥 <b>Рефералы:</b>\n"
    if history['referrals']:
        text += f"Всего: {len(history['referrals'])}\n"
    else:
        text += "Нет рефералов\n"
    text += "\n🎰 <b>Казино:</b>\n"
    if history['casino']:
        total_bet = sum(g[0] for g in history['casino'])
        total_win = sum(g[2] for g in history['casino'])
        text += f"Игр: {len(history['casino'])}, ставок: {total_bet} ⭐, выигрыш: {total_win} ⭐\n"
    else:
        text += "Нет игр\n"
    text += "\n📋 <b>Выполненные задания:</b>\n"
    if history['tasks']:
        text += f"Всего: {len(history['tasks'])}\n"
    else:
        text += "Нет выполненных заданий\n"
    keyboard = get_back_to_menu_keyboard()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

# -------------------- АДМИН-ПАНЕЛЬ --------------------
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    keyboard = get_admin_panel_keyboard()
    await message.answer(
        "🛠 <b>Административная панель</b>\n\n"
        "Выберите действие:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'admin_stats')
async def admin_stats(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    stats = db.get_user_stats()
    text = get_stats_text(
        stats['total_users'],
        stats['total_stars'],
        stats['total_channels'],
        stats['total_referrals'],
        stats['total_earned_refs']
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=get_back_to_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data == 'admin_channels')
async def admin_channels_menu(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    channels = db.get_channels()
    text = "📋 <b>Управление каналами</b>\n\n"
    if channels:
        for ch in channels:
            ch_id, channel_id, username, link, ctype, required, deadline, max_sub, cur_sub = ch
            status = "🔴 обязательный" if required else "🟢 задание"
            deadline_str = f" до {deadline}" if deadline else ""
            limit_str = f" лимит {cur_sub}/{max_sub}" if max_sub > 0 else ""
            text += f"• {username or channel_id} ({status}{deadline_str}{limit_str})\n"
    else:
        text += "Нет каналов\n"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить канал", callback_data="admin_add_channel"),
        InlineKeyboardButton("🗑 Удалить канал", callback_data="admin_del_channel"),
        InlineKeyboardButton("📊 Статистика канала", callback_data="admin_channel_stats"),
        InlineKeyboardButton("◀️ Назад", callback_data="admin")
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'admin_add_channel')
async def admin_add_channel_start(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "➕ <b>Добавление канала</b>\n\n"
        "Введите username канала (например @channel):",
        parse_mode='HTML'
    )
    await AdminAddChannel.waiting_for_username.set()

@dp.message_handler(state=AdminAddChannel.waiting_for_username)
async def admin_add_channel_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    await state.update_data(username=username)
    await message.answer(
        "Введите срок действия задания (в часах) или 0, если бессрочно:"
    )
    await AdminAddChannel.waiting_for_deadline.set()

@dp.message_handler(state=AdminAddChannel.waiting_for_deadline)
async def admin_add_channel_deadline(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
        if hours < 0:
            raise ValueError
    except:
        await message.answer("❌ Введите целое число часов (0 для бессрочно)")
        return
    deadline = None
    if hours > 0:
        deadline = datetime.now() + timedelta(hours=hours)
    await state.update_data(deadline=deadline)
    await message.answer(
        "Введите максимальное количество подписчиков (0 = без лимита):"
    )
    await AdminAddChannel.waiting_for_max_subscribers.set()

@dp.message_handler(state=AdminAddChannel.waiting_for_max_subscribers)
async def admin_add_channel_max_sub(message: types.Message, state: FSMContext):
    try:
        max_sub = int(message.text.strip())
        if max_sub < 0:
            raise ValueError
    except:
        await message.answer("❌ Введите целое число (0 = без лимита)")
        return
    data = await state.get_data()
    username = data['username']
    deadline = data['deadline']
    try:
        chat = await bot.get_chat(username)
        chat_member = await bot.get_chat_member(chat.id, bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.answer("❌ Бот не администратор в этом канале")
            await state.finish()
            return
        db.add_channel(
            channel_id=str(chat.id),
            channel_username=username,
            channel_type='public',
            channel_link=f"https://t.me/{chat.username}" if chat.username else None,
            is_required=False,
            deadline=deadline,
            max_subscribers=max_sub
        )
        db.log_admin_action(
            message.from_user.id,
            message.from_user.username,
            "add_channel",
            details=f"Канал {username}, срок {deadline}, лимит {max_sub}"
        )
        await message.answer(f"✅ Канал {username} добавлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.finish()
    await admin_panel(message)

@dp.callback_query_handler(lambda c: c.data == 'admin_channel_stats')
async def admin_channel_stats(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    channels = db.get_channels()
    if not channels:
        await bot.answer_callback_query(callback_query.id, "Нет каналов", show_alert=True)
        return
    text = "📊 <b>Статистика по каналам</b>\n\n"
    for ch in channels:
        ch_id, channel_id, username, link, ctype, required, deadline, max_sub, cur_sub = ch
        if required:
            continue
        total_users = db.cursor.execute('SELECT COUNT(*) FROM user_channels WHERE channel_id = ? AND completed = 1', (ch_id,)).fetchone()[0]
        text += f"• {username or channel_id}: выполнено {total_users} чел."
        if max_sub > 0:
            text += f" (лимит {cur_sub}/{max_sub})"
        if deadline:
            deadline_dt = datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
            if deadline_dt < datetime.now():
                text += " (истек)"
            else:
                remain = deadline_dt - datetime.now()
                text += f" (осталось {remain.days} дн. {remain.seconds//3600} ч.)"
        text += "\n"
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=get_back_to_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data == 'admin_events')
async def admin_events_menu(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    events = db.get_all_events()
    text = "🎉 <b>Управление ивентами</b>\n\n"
    if events:
        for e in events:
            eid, name, etype, mult, bonus, start, end, active = e
            status = "🟢 активен" if active else "🔴 неактивен"
            text += f"• {name} ({etype}) {status}\n"
    else:
        text += "Нет ивентов\n"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Создать ивент", callback_data="admin_create_event"),
        InlineKeyboardButton("❌ Удалить ивент", callback_data="admin_delete_event"),
        InlineKeyboardButton("🔄 Вкл/Выкл", callback_data="admin_toggle_event"),
        InlineKeyboardButton("◀️ Назад", callback_data="admin")
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'admin_create_event')
async def admin_create_event_start(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "🎉 <b>Создание ивента</b>\n\n"
        "Введите название ивента:",
        parse_mode='HTML'
    )
    await AdminCreateEvent.waiting_for_name.set()

@dp.message_handler(state=AdminCreateEvent.waiting_for_name)
async def admin_create_event_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer(
        "Выберите тип ивента:\n"
        "• referral - повышенная награда за рефералов\n"
        "• casino - повышенный множитель в казино\n"
        "• task - повышенная награда за задания\n"
        "Введите тип:"
    )
    await AdminCreateEvent.waiting_for_type.set()

@dp.message_handler(state=AdminCreateEvent.waiting_for_type)
async def admin_create_event_type(message: types.Message, state: FSMContext):
    etype = message.text.strip().lower()
    if etype not in ['referral', 'casino', 'task']:
        await message.answer("❌ Неверный тип. Введите referral, casino или task")
        return
    await state.update_data(etype=etype)
    await message.answer(
        "Введите множитель (например, 2 для x2, 5 для x5):"
    )
    await AdminCreateEvent.waiting_for_multiplier.set()

@dp.message_handler(state=AdminCreateEvent.waiting_for_multiplier)
async def admin_create_event_multiplier(message: types.Message, state: FSMContext):
    try:
        mult = int(message.text.strip())
        if mult < 1:
            raise ValueError
    except:
        await message.answer("❌ Введите целое число больше 0")
        return
    await state.update_data(mult=mult)
    await message.answer(
        "Введите бонус (дополнительные звезды, если нужен):"
    )
    await AdminCreateEvent.waiting_for_bonus.set()

@dp.message_handler(state=AdminCreateEvent.waiting_for_bonus)
async def admin_create_event_bonus(message: types.Message, state: FSMContext):
    try:
        bonus = int(message.text.strip())
    except:
        bonus = 0
    await state.update_data(bonus=bonus)
    await message.answer(
        "Введите длительность в часах:"
    )
    await AdminCreateEvent.waiting_for_duration.set()

@dp.message_handler(state=AdminCreateEvent.waiting_for_duration)
async def admin_create_event_duration(message: types.Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите целое число часов больше 0")
        return
    data = await state.get_data()
    event_id = db.create_event(
        name=data['name'],
        event_type=data['etype'],
        multiplier=data['mult'],
        bonus=data['bonus'],
        duration_hours=duration
    )
    db.log_admin_action(
        message.from_user.id,
        message.from_user.username,
        "create_event",
        details=f"Ивент {data['name']} (ID {event_id})"
    )
    await message.answer(f"✅ Ивент создан! ID {event_id}")
    await state.finish()
    await admin_panel(message)

@dp.callback_query_handler(lambda c: c.data == 'admin_logs')
async def admin_logs(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    logs = db.get_admin_logs(20)
    text = "📜 <b>Логи действий администраторов</b>\n\n"
    if logs:
        for log in logs:
            admin_id, admin_username, action, target, details, created = log
            text += f"• {created} @{admin_username}: {action}"
            if target:
                text += f" (цель: {target})"
            if details:
                text += f" — {details}"
            text += "\n"
    else:
        text += "Логов пока нет."
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=get_back_to_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data == 'admin_export')
async def admin_export(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    users = db.get_all_users_full()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['user_id', 'username', 'balance', 'referrals', 'earned_from_refs', 'last_active', 'banned', 'casino_win', 'casino_loss'])
    for u in users:
        writer.writerow(u)
    output.seek(0)
    document = InputFile(output, filename='users_export.csv')
    await bot.send_document(callback_query.from_user.id, document)
    await bot.answer_callback_query(callback_query.id, "✅ Экспорт выполнен")

@dp.callback_query_handler(lambda c: c.data == 'admin_backup')
async def admin_backup(callback_query: types.CallbackQuery):
    if not is_tech_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Только тех.админ может создавать бэкапы", show_alert=True)
        return
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(BACKUP_PATH, backup_filename)
    os.makedirs(BACKUP_PATH, exist_ok=True)
    shutil.copy2(DB_NAME, backup_path)
    await bot.send_document(callback_query.from_user.id, InputFile(backup_path))
    await bot.answer_callback_query(callback_query.id, "✅ Резервная копия создана и отправлена")

@dp.callback_query_handler(lambda c: c.data == 'admin_hunt')
async def admin_hunt(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    global HUNT_777_BROADCAST
    status = "включена" if HUNT_777_BROADCAST else "выключена"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Включить", callback_data="hunt_on"),
        InlineKeyboardButton("❌ Выключить", callback_data="hunt_off"),
        InlineKeyboardButton("◀️ Назад", callback_data="admin")
    )
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        f"🎯 <b>Охота за 777</b>\n\n"
        f"Текущий статус: {status}\n\n"
        f"При выпадении 777 сообщение будет отправляться всем.",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data in ['hunt_on', 'hunt_off'])
async def hunt_toggle(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    global HUNT_777_BROADCAST
    HUNT_777_BROADCAST = (callback_query.data == 'hunt_on')
    db.log_admin_action(
        callback_query.from_user.id,
        callback_query.from_user.username,
        "toggle_hunt",
        details=f"Охота за 777 теперь {'включена' if HUNT_777_BROADCAST else 'выключена'}"
    )
    await bot.answer_callback_query(callback_query.id, f"✅ Охота {'включена' if HUNT_777_BROADCAST else 'выключена'}")
    await admin_hunt(callback_query)

@dp.callback_query_handler(lambda c: c.data == 'admin_ban')
async def admin_ban_menu(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "🚫 <b>Бан / Разбан</b>\n\n"
        "Введите ID или @username пользователя:",
        parse_mode='HTML'
    )
    await AdminBanState.waiting_for_user.set()

@dp.message_handler(state=AdminBanState.waiting_for_user)
async def admin_ban_user_input(message: types.Message, state: FSMContext):
    identifier = message.text.strip().replace('@', '')
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except:
        user = db.get_user_by_username(identifier)
        user_id = user[0] if user else None
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.finish()
        return
    await state.update_data(user_id=user_id)
    banned = db.is_banned(user_id)
    if banned:
        await message.answer(
            f"Пользователь {identifier} уже забанен. Хотите разбанить?\n"
            "Введите 'разбан' для разбана, или причину бана для повторного бана:"
        )
    else:
        await message.answer("Введите причину бана (или отправьте 'пропустить'):")
    await AdminBanState.waiting_for_reason.set()

@dp.message_handler(state=AdminBanState.waiting_for_reason)
async def admin_ban_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    reason = message.text.strip()
    if reason.lower() == 'разбан':
        db.unban_user(user_id)
        await message.answer(f"✅ Пользователь {user_id} разбанен")
        db.log_admin_action(message.from_user.id, message.from_user.username, "unban", target_user_id=user_id)
    else:
        if reason.lower() == 'пропустить':
            reason = None
        db.ban_user(user_id, message.from_user.id, reason)
        await message.answer(f"✅ Пользователь {user_id} забанен")
        db.log_admin_action(message.from_user.id, message.from_user.username, "ban", target_user_id=user_id, details=reason)
    await state.finish()
    await admin_panel(message)

@dp.callback_query_handler(lambda c: c.data == 'admin_search')
async def admin_search(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите ID или @username:",
        parse_mode='HTML'
    )
    await AdminSearchState.waiting_for_query.set()

@dp.message_handler(state=AdminSearchState.waiting_for_query)
async def admin_search_query(message: types.Message, state: FSMContext):
    identifier = message.text.strip().replace('@', '')
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except:
        user = db.get_user_by_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.finish()
        return
    user_id = user[0]
    username = user[1] or "Нет username"
    balance = db.get_balance(user_id)
    banned = db.is_banned(user_id)
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{username}\n"
        f"💰 Баланс: {balance} ⭐\n"
        f"🚫 Бан: {'Да' if banned else 'Нет'}\n"
    )
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📜 История", callback_data=f"admin_history_{user_id}"),
        InlineKeyboardButton("💰 Начислить", callback_data=f"admin_give_{user_id}"),
        InlineKeyboardButton("💸 Списать", callback_data=f"admin_take_{user_id}"),
        InlineKeyboardButton("🚫 Забанить", callback_data=f"admin_ban_{user_id}"),
        InlineKeyboardButton("◀️ Назад", callback_data="admin")
    )
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('admin_history_'))
async def admin_user_history(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(callback_query.id, "❌ Доступ запрещен", show_alert=True)
        return
    user_id = int(callback_query.data.split('_')[2])
    history = db.get_user_full_history(user_id)
    text = f"📜 <b>История пользователя {user_id}</b>\n\n"
    text += f"💰 <b>Транзакции:</b>\n"
    for t in history['transactions'][:10]:
        amount, ttype, desc, date = t
        sign = "+" if amount > 0 else ""
        date_str = date.split()[0] if date else ""
        text += f"  {sign}{amount} ⭐ — {desc} ({date_str})\n"
    text += f"\n👥 <b>Рефералы:</b> {len(history['referrals'])}\n"
    text += f"🎰 <b>Казино:</b> {len(history['casino'])} игр\n"
    text += f"📋 <b>Задания:</b> {len(history['tasks'])}\n"
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=get_back_to_menu_keyboard())

@dp.message_handler(commands=['history'])
async def cmd_history(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /history @username или ID")
        return
    identifier = args[1].replace('@', '')
    try:
        user_id = int(identifier)
    except:
        user = db.get_user_by_username(identifier)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        user_id = user[0]
    history = db.get_user_full_history(user_id)
    output = io.StringIO()
    output.write(f"История пользователя {user_id}\n\n")
    output.write("Транзакции:\n")
    for t in history['transactions']:
        output.write(f"{t}\n")
    output.write("\nРефералы:\n")
    for r in history['referrals']:
        output.write(f"{r}\n")
    output.write("\nКазино:\n")
    for c in history['casino']:
        output.write(f"{c}\n")
    output.write("\nЗадания:\n")
    for t in history['tasks']:
        output.write(f"{t}\n")
    output.seek(0)
    document = InputFile(output, filename=f'history_{user_id}.txt')
    await message.reply_document(document)

# -------------------- СТАРЫЕ АДМИНСКИЕ КОМАНДЫ (ИЗ НАЧАЛЬНОГО КОДА) --------------------
# /addkanal
@dp.message_handler(commands=['addkanal'])
async def cmd_add_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.get_args()
    if args:
        await process_add_channel(message, args)
    else:
        await message.answer(
            "📝 <b>Добавление канала</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/addkanal @username_канала</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/addkanal @my_channel</code>\n\n"
            "⚠️ <b>Требования:</b>\n"
            "• Бот должен быть администратором канала",
            parse_mode='HTML'
        )

async def process_add_channel(message: types.Message, channel_username: str):
    if not channel_username.startswith('@'):
        channel_username = '@' + channel_username
    try:
        chat = await bot.get_chat(channel_username)
        chat_member = await bot.get_chat_member(chat.id, bot.id)
        if chat_member.status in ['administrator', 'creator']:
            existing = db.get_channel_by_username(channel_username)
            if existing:
                await message.answer(f"❌ Канал {channel_username} уже добавлен!")
                return
            db.add_channel(str(chat.id), channel_username, 'public', None, False)
            await message.answer(
                f"✅ <b>Канал добавлен!</b>\n\n"
                f"📢 <b>Название:</b> {channel_username}\n"
                f"🆔 <b>ID:</b> {chat.id}\n"
                f"👥 <b>Участники:</b> {chat.members_count if hasattr(chat, 'members_count') else 'Неизвестно'}\n\n"
                f"🎯 <b>Статус:</b> Активен\n"
                f"💰 <b>Награда:</b> 2 звезды",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка доступа</b>\n\n"
                f"Бот не является администратором в канале {channel_username}!\n\n"
                f"💡 <b>Решение:</b>\n"
                f"1. Добавьте бота в канал\n"
                f"2. Назначьте права администратора\n"
                f"3. Попробуйте снова",
                parse_mode='HTML'
            )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}\n\n"
            f"💡 <b>Проверьте:</b>\n"
            "• Существует ли канал\n"
            "• Правильно ли указан username\n"
            "• Доступен ли канал",
            parse_mode='HTML'
        )

# /addidkanal
@dp.message_handler(commands=['addidkanal'])
async def cmd_add_channel_by_id(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "📝 <b>Добавление приватного канала</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/addidkanal [ID_канала] [ссылка]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/addidkanal -1001234567890 https://t.me/private_channel</code>\n\n"
            "🔑 <b>Как получить ID:</b>\n"
            "1. Добавьте бота @getidsbot в канал\n"
            "2. Получите ID канала\n"
            "3. ID начинается с -100",
            parse_mode='HTML'
        )
        return
    channel_id = args[1]
    channel_link = args[2]
    if not channel_link.startswith(('https://t.me/', 'https://telegram.me/', '@')):
        await message.answer(
            "❌ <b>Неверная ссылка</b>\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://t.me/username\n"
            "• https://telegram.me/username\n"
            "• @username",
            parse_mode='HTML'
        )
        return
    try:
        chat = await bot.get_chat(channel_id)
        chat_member = await bot.get_chat_member(chat.id, bot.id)
        if chat_member.status in ['administrator', 'creator']:
            existing = db.get_channel_by_id(channel_id)
            if existing:
                await message.answer(f"❌ Канал с ID {channel_id} уже добавлен!")
                return
            db.add_channel(channel_id, None, 'private', channel_link, False)
            await message.answer(
                f"✅ <b>Приватный канал добавлен!</b>\n\n"
                f"🔒 <b>Тип:</b> Приватный\n"
                f"🆔 <b>ID:</b> {channel_id}\n"
                f"🔗 <b>Ссылка:</b> {channel_link}\n"
                f"👥 <b>Участники:</b> {chat.members_count if hasattr(chat, 'members_count') else 'Неизвестно'}\n\n"
                f"🎯 <b>Статус:</b> Активен\n"
                f"💰 <b>Награда:</b> 2 звезды",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка доступа</b>\n\n"
                f"Бот не является администратором в канале!\n\n"
                f"💡 <b>Решение:</b>\n"
                f"1. Добавьте бота в канал\n"
                f"2. Назначьте права администратора\n"
                f"3. Убедитесь, что бот видит участников",
                parse_mode='HTML'
            )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}\n\n"
            f"💡 <b>Убедитесь, что:</b>\n"
            f"1. Бот добавлен в канал как администратор\n"
            f"2. ID канала указан верно (начинается с -100)\n"
            f"3. Канал существует и активен",
            parse_mode='HTML'
        )

# /addrequired
@dp.message_handler(commands=['addrequired'])
async def cmd_add_required_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "📢 <b>Добавление обязательного канала</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/addrequired [ID_канала] [ссылка]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/addrequired -1001234567890 https://t.me/required_channel</code>\n\n"
            "⚠️ <b>Внимание:</b>\n"
            "• Этот канал будет обязательным для всех пользователей\n"
            "• Без подписки на него бот не будет работать",
            parse_mode='HTML'
        )
        return
    channel_id = args[1]
    channel_link = args[2]
    if not channel_link.startswith(('https://t.me/', 'https://telegram.me/', '@')):
        await message.answer(
            "❌ <b>Неверная ссылка</b>\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://t.me/username\n"
            "• https://telegram.me/username\n"
            "• @username",
            parse_mode='HTML'
        )
        return
    try:
        chat = await bot.get_chat(channel_id)
        chat_member = await bot.get_chat_member(chat.id, bot.id)
        if chat_member.status in ['administrator', 'creator']:
            existing = db.get_channel_by_id(channel_id)
            if existing:
                cursor = db.conn.cursor()
                cursor.execute('UPDATE channels SET is_required = 1 WHERE channel_id = ?', (channel_id,))
                db.conn.commit()
            else:
                db.add_channel(channel_id, None, 'private', channel_link, True)
            await message.answer(
                f"✅ <b>Обязательный канал добавлен!</b>\n\n"
                f"🔒 <b>Тип:</b> Обязательный для подписки\n"
                f"🆔 <b>ID:</b> {channel_id}\n"
                f"🔗 <b>Ссылка:</b> {channel_link}\n"
                f"👥 <b>Участники:</b> {chat.members_count if hasattr(chat, 'members_count') else 'Неизвестно'}\n\n"
                f"🎯 <b>Статус:</b> Обязательный\n"
                f"⚠️ <b>Все пользователи должны подписаться на этот канал!</b>",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка доступа</b>\n\n"
                f"Бот не является администратором в канале!\n\n"
                f"💡 <b>Решение:</b>\n"
                f"1. Добавьте бота в канал\n"
                f"2. Назначьте права администратора\n"
                f"3. Убедитесь, что бот видит участников",
                parse_mode='HTML'
            )
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)}\n\n"
            f"💡 <b>Убедитесь, что:</b>\n"
            f"1. Бот добавлен в канал как администратор\n"
            f"2. ID канала указан верно (начинается с -100)\n"
            f"3. Канал существует и активен",
            parse_mode='HTML'
        )

# /listkanal
@dp.message_handler(commands=['listkanal'])
async def cmd_list_channels(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    channels = db.get_channels()
    if not channels:
        await message.answer("📭 Список каналов пуст")
        return
    response = "📋 <b>Список каналов:</b>\n\n"
    for idx, channel in enumerate(channels, 1):
        channel_id, channel_username, channel_link, channel_type, is_required = channel[:5]
        required_mark = " (обязательный)" if is_required else ""
        if channel_type == 'public':
            response += f"{idx}. {channel_username} (публичный){required_mark}\n"
        else:
            response += f"{idx}. ID: {channel_id} | Ссылка: {channel_link} (приватный){required_mark}\n"
    await message.answer(response, parse_mode='HTML')

# /addpromo
@dp.message_handler(commands=['addpromo'])
async def cmd_add_promo(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 4:
        await message.answer(
            "🎁 <b>Создание промокода</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/addpromo [код] [звезды] [активации]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/addpromo SUMMER2024 50 100</code>\n\n"
            "✨ <b>Расшифровка:</b>\n"
            "• SUMMER2024 - код промокода\n"
            "• 50 - количество звезд\n"
            "• 100 - количество активаций",
            parse_mode='HTML'
        )
        return
    promo_code = args[1]
    try:
        stars = int(args[2])
        activations = int(args[3])
    except ValueError:
        await message.answer("❌ Звёзды и активации должны быть числами!")
        return
    if stars <= 0 or activations <= 0:
        await message.answer("❌ Звёзды и активации должны быть больше 0!")
        return
    db.add_promo(promo_code, stars, activations)
    await message.answer(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎁 <b>Код:</b> <code>{promo_code.upper()}</code>\n"
        f"⭐ <b>Награда:</b> {stars} звезд\n"
        f"🔢 <b>Активаций:</b> {activations}\n"
        f"📅 <b>Создан:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"🎯 <b>Статус:</b> Активен\n"
        f"👥 <b>Могут активировать:</b> {activations} пользователей",
        parse_mode='HTML'
    )

# /delpromo
@dp.message_handler(commands=['delpromo'])
async def cmd_del_promo(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.get_args()
    if not args:
        await message.answer(
            "🗑️ <b>Удаление промокода</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/delpromo [код]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/delpromo SUMMER2024</code>\n\n"
            "⚠️ <b>Внимание:</b>\n"
            "• Промокод будет удален\n"
            "• Активации прекратятся\n"
            "• Действие нельзя отменить",
            parse_mode='HTML'
        )
        return
    promo_code = args
    db.delete_promo(promo_code)
    await message.answer(
        f"✅ <b>Промокод удален!</b>\n\n"
        f"🎁 <b>Код:</b> <code>{promo_code.upper()}</code>\n"
        f"🗑️ <b>Статус:</b> Удален\n"
        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"👥 <b>Пользователи больше не смогут его активировать</b>",
        parse_mode='HTML'
    )

# /listpromo
@dp.message_handler(commands=['listpromo'])
async def cmd_list_promo(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    promos = db.get_all_promos()
    if not promos:
        await message.answer("📭 Список промокодов пуст")
        return
    response = "🎁 <b>Список промокодов:</b>\n\n"
    for promo in promos:
        promo_code, stars, max_activations, used_activations = promo
        status = "🟢 Активен" if used_activations < max_activations else "🔴 Закончился"
        response += f"• <code>{promo_code}</code>: {stars}⭐ ({used_activations}/{max_activations}) {status}\n"
    await message.answer(response, parse_mode='HTML')

# /stats
@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    stats = db.get_user_stats()
    text = get_stats_text(
        stats['total_users'],
        stats['total_stars'],
        stats['total_channels'],
        stats['total_referrals'],
        stats['total_earned_refs']
    )
    await message.answer(text, parse_mode='HTML')

# /news
@dp.message_handler(commands=['news'])
async def cmd_news(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    news_text = message.text.replace('/news', '').strip()
    if not news_text:
        await message.answer(
            "📢 <b>Рассылка новостей</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/news [текст новости]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/news У нас новая акция! Получите 50 звезд по промокоду NEWYEAR</code>\n\n"
            "⚠️ <b>Внимание:</b>\n"
            "• Новость будет отправлена всем пользователям\n"
            "• Действие нельзя отменить",
            parse_mode='HTML'
        )
        return
    all_users = db.get_all_users()
    total_users = len(all_users)
    success_sent = 0
    failed_sent = 0
    status_message = await message.answer(
        f"📢 <b>Начинаю рассылку новостей...</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {total_users}\n"
        f"📝 <b>Текст новости:</b>\n{news_text[:100]}...\n\n"
        f"⏳ <b>Статус:</b> В процессе",
        parse_mode='HTML'
    )
    for user in all_users:
        user_id = user[0]
        try:
            await bot.send_message(
                user_id,
                f"📢 <b>НОВОСТИ</b>\n\n"
                f"{news_text}\n\n"
                f"<i>С уважением, команда STILNI BOT</i>",
                parse_mode='HTML'
            )
            success_sent += 1
            if success_sent % 50 == 0:
                await status_message.edit_text(
                    f"📢 <b>Рассылка новостей...</b>\n\n"
                    f"👥 <b>Всего пользователей:</b> {total_users}\n"
                    f"✅ <b>Отправлено успешно:</b> {success_sent}\n"
                    f"❌ <b>Не отправлено:</b> {failed_sent}\n"
                    f"📊 <b>Прогресс:</b> {int((success_sent + failed_sent) / total_users * 100)}%\n\n"
                    f"⏳ <b>Статус:</b> В процессе",
                    parse_mode='HTML'
                )
            await asyncio.sleep(0.05)
        except Exception as e:
            failed_sent += 1
            print(f"Не удалось отправить новость пользователю {user_id}: {e}")
    await status_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Итоги:</b>\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Успешно отправлено: {success_sent}\n"
        f"• Не удалось отправить: {failed_sent}\n"
        f"• Процент успеха: {int(success_sent / total_users * 100 if total_users > 0 else 0)}%\n\n"
        f"📝 <b>Текст новости:</b>\n{news_text[:200]}...\n\n"
        f"⏰ <b>Время завершения:</b> {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML'
    )
    await message.answer(
        f"📢 <b>Рассылка новостей завершена!</b>\n\n"
        f"✅ <b>Успешно:</b> {success_sent} пользователей\n"
        f"❌ <b>Ошибки:</b> {failed_sent} пользователей\n"
        f"👤 <b>Отправил:</b> @{message.from_user.username}\n"
        f"⏰ <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='HTML'
    )

# /delstars
@dp.message_handler(commands=['delstars'])
async def cmd_delstars(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "💰 <b>Списание звезд у пользователя</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/delstars @username количество</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/delstars @username 50</code>\n\n"
            "⚠️ <b>Внимание:</b>\n"
            "• Нельзя списать больше, чем есть на балансе\n"
            "• Баланс не может быть отрицательным",
            parse_mode='HTML'
        )
        return
    identifier = args[1].replace('@', '')
    try:
        amount = int(args[2])
        if amount <= 0:
            await message.answer("❌ Количество должно быть положительным числом!")
            return
    except ValueError:
        await message.answer("❌ Количество должно быть числом!")
        return
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except ValueError:
        user = db.get_user_by_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    user_id = user[0]
    username = user[1] if len(user) > 1 else identifier
    current_balance = db.get_balance(user_id)
    if amount > current_balance:
        amount = current_balance
    db.update_balance(user_id, -amount, f"Списание администратором @{message.from_user.username}")
    await message.answer(
        f"✅ <b>Списание выполнено!</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"💰 <b>Списано:</b> {amount} звезд\n"
        f"💎 <b>Было:</b> {current_balance} звезд\n"
        f"🆕 <b>Стало:</b> {db.get_balance(user_id)} звезд\n\n"
        f"👨‍💼 <b>Администратор:</b> @{message.from_user.username}\n"
        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML'
    )

# /givestars
@dp.message_handler(commands=['givestars'])
async def cmd_givestars(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "🎁 <b>Выдача звезд пользователю</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/givestars @username количество</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/givestars @username 100</code>\n\n"
            "✨ <b>Максимум:</b> 1000000 звезд за раз",
            parse_mode='HTML'
        )
        return
    identifier = args[1].replace('@', '')
    try:
        amount = int(args[2])
        if amount <= 0:
            await message.answer("❌ Количество должно быть положительным числом!")
            return
        if amount > 1000000:
            await message.answer("❌ Слишком большое количество! Максимум 1,000,000 звезд.")
            return
    except ValueError:
        await message.answer("❌ Количество должно быть числом!")
        return
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except ValueError:
        user = db.get_user_by_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    user_id = user[0]
    username = user[1] if len(user) > 1 else identifier
    current_balance = db.get_balance(user_id)
    db.update_balance(user_id, amount, f"Выдача администратором @{message.from_user.username}")
    await message.answer(
        f"✅ <b>Выдача выполнена!</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"💰 <b>Выдано:</b> {amount} звезд\n"
        f"💎 <b>Было:</b> {current_balance} звезд\n"
        f"🆕 <b>Стало:</b> {db.get_balance(user_id)} звезд\n\n"
        f"👨‍💼 <b>Администратор:</b> @{message.from_user.username}\n"
        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML'
    )

# /checksub
@dp.message_handler(commands=['checksub'])
async def cmd_checksub(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Эта команда только для администратора!")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Принудительная проверка подписки</b>\n\n"
            "📌 <b>Использование:</b>\n"
            "<code>/checksub @username</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/checksub @username</code>\n\n"
            "📊 <b>Можно также по ID:</b>\n"
            "<code>/checksub 1234567890</code>",
            parse_mode='HTML'
        )
        return
    identifier = args[1].replace('@', '')
    try:
        user_id = int(identifier)
        user = db.get_user(user_id)
    except ValueError:
        user = db.get_user_by_username(identifier)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    user_id = user[0]
    username = user[1] if len(user) > 1 else identifier
    is_subscribed = await check_required_channel_subscription(bot, user_id)
    if is_subscribed:
        status_text = "✅ Подписан на обязательный канал"
    else:
        status_text = "❌ НЕ подписан на обязательный канал"
    registration_completed = db.is_registration_completed(user_id)
    if registration_completed:
        reg_text = "✅ Регистрация завершена"
    else:
        reg_text = "❌ Регистрация не завершена"
    await message.answer(
        f"🔍 <b>Проверка подписки пользователя</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"🆔 <b>ID:</b> {user_id}\n\n"
        f"📊 <b>Статус:</b>\n"
        f"• Подписка: {status_text}\n"
        f"• Регистрация: {reg_text}\n\n"
        f"⏰ <b>Время проверки:</b> {datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML'
    )