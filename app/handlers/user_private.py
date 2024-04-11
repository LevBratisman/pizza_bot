from aiogram import F, Router
from aiogram import types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.orm_query import orm_add_to_cart, orm_add_user, orm_get_user_carts, orm_get_product, orm_add_order
from app.filters.chat_type import ChatTypeFilter
from app.handlers.menu_processing import get_menu_content
from app.keyboards.inline import MenuCallBack, get_callback_btns
from app.keyboards.reply import get_keyboard


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(['private']))

@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    
    user = message.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
    )
    
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")

    await message.answer_photo(media.media, 
                               caption=media.caption, 
                               reply_markup=reply_markup, 
                               parse_mode="HTML")
    
    
@user_private_router.callback_query(CommandStart())
async def start_cmd_callback(callback: types.CallbackQuery, session: AsyncSession):
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    await callback.message.answer_photo(media.media, 
                               caption=media.caption, 
                               reply_markup=reply_markup, 
                               parse_mode="HTML")


async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.answer("Товар добавлен в корзину.")
    
    

@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession, state: FSMContext):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return
    
    if callback_data.menu_name == "order":
        await form_order(callback, callback_data, state)
        return

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, 
                                      reply_markup=reply_markup, 
                                      parse_mode="HTML")
    await callback.answer()
    
    
    
############################## ОФОРМЛЕНИЕ ЗАКАЗА ##############################

class GetOrder(StatesGroup):
    user_id = State()
    phone = State()
    address = State()
    products = State()
    total_price = State()
    confirmation = State()
    
    
    
@user_private_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    await message.answer("Заказ отменен", reply_markup=ReplyKeyboardRemove())
    await start_cmd(message, session)
    

@user_private_router.callback_query(MenuCallBack.filter())
async def form_order(callback: types.Message, callback_data: MenuCallBack, state: FSMContext):
    if callback_data.menu_name == "order":
        await callback.message.delete()
        await callback.message.answer_sticker('CAACAgIAAxkBAAIQEmYDxSY6C4KfJa-YPz_z3dGnXJshAAJcAAPkoM4Hmml1PMpcRTs0BA')
        await asyncio.sleep(1)
        await callback.answer("Оформление заказа", reply_markup=get_keyboard(
            "Отмена",
            "Назад",
            placehoder="Заполните информацию о заказе"
        ))
        await state.set_state(GetOrder.phone)
        await callback.message.answer("Введите ваш номер телефона")
    
    
@user_private_router.message(StateFilter(GetOrder.phone), F.text)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Введите ваш адрес")
    await state.set_state(GetOrder.address)
    
    
@user_private_router.message(StateFilter(GetOrder.phone))
async def check_confirmation(message: types.Message):
    await message.answer("Неверный формат, введите номер заново")
    
    
@user_private_router.message(StateFilter(GetOrder.address), F.text)
async def get_address(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.update_data(address=message.text)
    
    data = await state.get_data()
    products = await orm_get_user_carts(session, user_id=message.from_user.id)
    total_cost = 0
    
    list_products = ''
    
    await message.answer(f"Информация о заказе:\n\n" +
                         f"<b>Телефон</b>: {data['phone']}\n<b>Адрес</b>: {data['address']}\n\n" +
                         "<b>Товары</b>:")
    for product in products:
        product_info = await orm_get_product(session, product_id=product.product_id)
        await message.answer(f"------------------------------\n" +
                             f"Название: {product_info.name}\nЦена: {product_info.price}$\nКоличество: {product.quantity}\n" +
                             "------------------------------\n")
        list_products += f"{product_info.id}:{product.quantity};"
        total_cost += product_info.price * product.quantity
    
    await message.answer("<i>Итого</i>: " + str(total_cost) + "$")
    
    await state.update_data(user_id=int(message.from_user.id))
    await state.update_data(products=list_products)
    await state.update_data(total_price=total_cost)
    
    await asyncio.sleep(1)
    await message.answer("Подтвердите заказ", reply_markup=get_callback_btns(btns={
        "Подтвердить": "confirm",
        "Отмена": "cancel"
    }))
    await state.set_state(GetOrder.confirmation)
    
    
@user_private_router.message(StateFilter(GetOrder.address))
async def check_confirmation(message: types.Message):
    await message.answer("Неверный формат, введите адрес заново")

    
    
@user_private_router.callback_query(StateFilter(GetOrder.confirmation), F.data)
async def get_confirmation(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.data == "confirm":
        data = await state.get_data()
        await orm_add_order(session, data)
        await callback.message.answer_sticker('CAACAgIAAxkBAAIQFGYDxkqMP31aAiVSKLoSRPzhVsqfAAIcAQACMNSdEW7qjCmqrhdONAQ')
        await asyncio.sleep(1)
        await callback.answer("Заказ оформлен")
    elif callback.data == "cancel":
        await callback.answer("Заказ отменен")
    await callback.message.delete()
    await state.clear()
    await start_cmd_callback(callback, session)
        
        
@user_private_router.message(StateFilter(GetOrder.confirmation))
async def check_confirmation(message: types.Message):
    await message.answer("Нажмите на кнопку, чтобы подтвердить заказ")
        
    
###############################################################################