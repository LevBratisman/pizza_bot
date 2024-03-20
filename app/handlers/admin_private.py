from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.orm_query import orm_add_product, orm_delete_product, orm_get_product, orm_get_products, orm_update_product
from app.keyboards.inline import get_callback_btns
from app.keyboards.reply import get_keyboard
from app.filters.admin import IsAdmin
from app.filters.chat_type import ChatTypeFilter

admin_private_router = Router()
admin_private_router.message.filter(ChatTypeFilter(['private']), IsAdmin())


######################### КЛАВИАТУРЫ ###############################################

ADMIN_KB = get_keyboard(
    "Добавить товар",
    "Ассортимент",
    "Выйти из админ панели",
    placehoder="Выберите действие",
    sizes=(2, 1)
)

state_process_kb = get_keyboard(
    "Назад",
    "Отмена",
    placehoder="Выберите действие"
)

#########################################################################################




class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    image = State()
    
    product_for_edit = None
    
    texts = {
        "AddProduct:name": "Введите название заново:",
        "AddProduct:description": "Введите описание заново:",
        "AddProduct:category": "Выберите категорию  заново ⬆️",
        "AddProduct:price": "Введите стоимость заново:",
        "AddProduct:image": "Этот стейт последний, поэтому...",
    }




######################### БАЗОВЫЕ ХЕНДЛЕРЫ ###############################################


@admin_private_router.message(Command("admin"))
async def admin_panel(message: Message):
    await message.answer("Вы зашли в админ панель", reply_markup=ADMIN_KB)
    
    
@admin_private_router.message(F.text=="Выйти из админ панели")
async def leave_admin_panel(message: Message):
    await message.answer("Вы вышли из админ панели", reply_markup=ReplyKeyboardRemove())
    
    
@admin_private_router.message(F.text=="Ассортимент")
async def show_products(message: Message, session: AsyncSession):
    await message.answer("Вот список товаров")
    for product in await orm_get_products(session):
        await message.answer_photo(product.image, 
                                   caption=f"Название: {product.name}\n" +
                                   f"Описание: {product.description}\n" +
                                   f"Цена: {round(product.price, 2)}", 
                                   reply_markup=get_callback_btns(btns={
                                       "Удалить": f"delete_{product.id}",
                                       "Изменить": f"edit_{product.id}"
                                   }))
        
        
@admin_private_router.callback_query(F.data.startswith("delete_"))
async def delete_product(callback: CallbackQuery, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    await orm_delete_product(session, int(product_id))
    await callback.message.delete()
    await callback.answer("Товар удален!")
    
    
@admin_private_router.callback_query(StateFilter(None), F.data.startswith("edit_"))
async def edit_product(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    product_id = callback.data.split("_")[-1]
    product_for_edit = await orm_get_product(session, int(product_id))
    
    AddProduct.product_for_edit = product_for_edit
    
    await callback.answer()
    await callback.message.answer("Введите новое название", reply_markup=state_process_kb)
    
    await state.set_state(AddProduct.name)
    

    
#########################################################################################



######################### FSM для дабавления/изменения товаров админом ##################


# Начало процесса добавления/изменения товара
@admin_private_router.message(StateFilter(None), F.text=="Добавить товар")
async def add_product(message: Message, state: FSMContext):
    await state.set_state(AddProduct.name)
    await message.answer("Введите название", reply_markup=state_process_kb)
    
    
# Завершение процесса добавления/изменения
@admin_private_router.message(StateFilter('*'), F.text.casefold()=="отмена")
async def reset_state(message: Message, state: FSMContext):
    
    current_state = await state.get_state()
    if AddProduct.product_for_edit:
        AddProduct.product_for_edit = None
    if current_state is None:
        return
    
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)
    
    
# Возврат назад
@admin_private_router.message(StateFilter('*'), F.text.casefold()=="назад")
async def get_back(message: Message, state: FSMContext):
    
    current_state = await state.get_state()
    if current_state == AddProduct.name:
        await message.answer("Предыдущего шага нет. Введите название товара или напишите 'отмена'")
        return
    
    previous_state = None
    for step in AddProduct.__all_states__:
        if step.state == current_state:
            await state.set_state(previous_state)
            await message.answer(f'Вы вернулись назад. {AddProduct.texts[previous_state]}')
            return
        else:
            previous_state = step
    
    
# Ввод названия
@admin_private_router.message(AddProduct.name, or_f(F.text, F.text == '.'))
async def get_name(message: Message, state: FSMContext):
    if message.text == '.':
        await state.update_data(name=AddProduct.product_for_edit.name)
    else:
        await state.update_data(name=message.text)
        
    await message.answer("Введите описание")
    await state.set_state(AddProduct.description)
    
# Хендлер для обработки некорректного ввода названия
@admin_private_router.message(AddProduct.name)
async def get_name(message: Message, state: FSMContext):
    await message.answer("Вы ввели некорректные данные. Введите название заново")

    
# Ввод описания
@admin_private_router.message(AddProduct.description, or_f(F.text, F.text == '.'))
async def get_description(message: Message, state: FSMContext):
    if message.text == '.':
        await state.update_data(description=AddProduct.product_for_edit.description)
    else:
        await state.update_data(description=message.text)
        
    await message.answer("Напишите цену")
    await state.set_state(AddProduct.price)
    
# Хендлер для обработки некорректного ввода описания
@admin_private_router.message(AddProduct.description)
async def get_name(message: Message, state: FSMContext):
    await message.answer("Вы ввели некорректные данные. Введите описание заново")
    
    
# Ввод цены
@admin_private_router.message(AddProduct.price, or_f(F.text, F.text == '.'))
async def get_price(message: Message, state: FSMContext):
    if message.text == '.':
        await state.update_data(price=AddProduct.product_for_edit.price)
    else:
        try:
            await state.update_data(price=float(message.text))
        except:
            await message.answer("Вы ввели некорректные данные. Введите цену заново")
            return
    await message.answer("Загрузите изображение")
    await state.set_state(AddProduct.image)
        
    
    
# Хендлер для обработки некорректного ввода цены
@admin_private_router.message(AddProduct.price)
async def get_name(message: Message, state: FSMContext):
    await message.answer("Вы ввели некорректные данные. Введите цену заново")
    
    
# Загрузка изображения
@admin_private_router.message(AddProduct.image, or_f(F.photo, F.text == '.'))
async def get_image(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == '.':
        await state.update_data(image=AddProduct.product_for_edit.image)
    else:
        await state.update_data(image=message.photo[-1].file_id)
        
    data = await state.get_data() 
        
    try:
        if AddProduct.product_for_edit:
            await orm_update_product(session, AddProduct.product_for_edit.id, data)
            await message.answer("Товар успешно изменен!", reply_markup=ADMIN_KB)
        else:
            await orm_add_product(session, data)
            await message.answer_photo(data["image"],
                                    caption=f"Название: {data['name']}\nОписание: {data['description']}\nЦена: {data['price']}")
            await message.answer("Товар успешно добавлен!", reply_markup=ADMIN_KB)
        await state.clear()
    except Exception as e:
        print(e)
        await message.answer("Произошла ошибка. Попробуйте ещё раз", reply_markup=ADMIN_KB)
        await state.clear()
        
    AddProduct.product_for_edit = None
    
# Хендлер для обработки некорректной загрузки изображения
@admin_private_router.message(AddProduct.image)
async def get_name(message: Message, state: FSMContext):
    await message.answer("Вы ввели некорректные данные. Загрузите изображение")