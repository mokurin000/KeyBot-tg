import asyncio
import json

from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Store admin ID
ADMIN_IDS = []
# Bot Token
BOT_TOKEN = ""

# provider_token left blank because physical goods are not involved
PROVIDER_TOKEN = ""

# Store product information and card keys
products = {}
card_keys = {}
payhistory = {}


# Load data from file
def load_data():
    global products, card_keys, payhistory
    try:
        with open("products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        with open("card_keys.json", "r", encoding="utf-8") as f:
            card_keys = json.load(f)
        with open("payhistory.json", "r", encoding="utf-8") as f:
            payhistory = json.load(f)
    except FileNotFoundError:
        products = {}
        card_keys = {}
        payhistory = {}


# Save data to file
def save_data():
    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products, f)
    with open("card_keys.json", "w", encoding="utf-8") as f:
        json.dump(card_keys, f)
    with open("payhistory.json", "w", encoding="utf-8") as f:
        json.dump(payhistory, f)


# Admin command to create a product
async def create_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        name, description, price = context.args
        price = int(price)
        products[name] = {"description": description, "price": price}
        card_keys[name] = []
        save_data()
        await update.message.reply_text(f"Product '{name}' created successfully!")
    except ValueError:
        await update.message.reply_text(
            "Please use the format: /create_product <name> <description> <price>"
        )


# Admin command to add card keys to a product
async def add_card_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        call_lines = update.message.text.split("\n")
        product_name = call_lines[0].split(maxsplit=1)[1]
        new_keys = map(lambda s: s.strip(), call_lines[1:])
        print(card_keys)
        if product_name in card_keys:
            card_keys[product_name].extend(new_keys)
            save_data()
            await update.message.reply_text(
                f"Card keys added to product '{product_name}'."
            )
        else:
            await update.message.reply_text("Product not found.")
    except IndexError:
        await update.message.reply_text(
            "Please use the format: /add_card_keys <product_name>\n<key1>\n<key2>\n..."
        )


# Admin command to check the inventory of card keys
async def check_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    inventory = "\n".join(
        [f"{k}: {len(v)} keys available" for k, v in card_keys.items()]
    )
    await update.message.reply_text(f"Current inventory:\n{inventory}")


# User command to start and show product list
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Register commands
    await context.bot.set_my_commands(
        [
            BotCommand("start", "Show the product list"),
            BotCommand("paysupport", "After-pay service"),
        ]
    )

    keyboard = [
        [InlineKeyboardButton(name, callback_data=name)] for name in products.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Please choose the product you want to purchase:", reply_markup=reply_markup
    )


# Handle product selection and initiate payment
async def product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    product_name = query.data
    await query.answer()

    product = products[product_name]
    title = f"Purchase {product_name}"
    description = product["description"]
    payload = f"purchase-{product_name}"
    currency = "XTR"  # Using stars for payment
    prices = [LabeledPrice(f"{product_name} card key", product["price"])]

    # Send payment information
    await query.message.reply_invoice(
        title=title,
        description=description,
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=currency,
        prices=prices,
        start_parameter="card-purchase",
        is_flexible=False,
    )


# Handle pre-checkout (check payment information)
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    payload = query.invoice_payload
    if not payload.startswith("purchase-"):
        await query.answer(ok=False, error_message="Error in payment information.")

    product_name = payload.split("-")[1]
    if product_name in card_keys and card_keys[product_name]:
        await query.answer(ok=True)
    else:
        await query.answer(
            ok=False, error_message=f"Sorry, {product_name} is out of stock."
        )


# Handle successful payment
async def successful_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    charge_id = update.message.successful_payment.telegram_payment_charge_id
    product_name = update.message.successful_payment.invoice_payload.split("-")[1]

    payhistory[user_id] = payhistory.get(user_id, []) + [charge_id]
    save_data()

    if product_name in card_keys and card_keys[product_name]:
        card_key = card_keys[product_name].pop(
            0
        )  # Send the first card key and remove it
        save_data()
        await update.message.reply_text(
            f"Thank you for your purchase! Your card key is: {card_key}\nCharge ID: {charge_id}"
        )
    else:
        await update.message.reply_text(
            f"Sorry, '{product_name}' is out of stock.\nCharge ID: {charge_id}"
        )


# Admin command to check the inventory of card keys
async def paysupport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in payhistory:
        innertext = "Sorry, but we found no transition related to you."
    else:
        innertext = f"""Your transitions:
{"\n".join(payhistory[user_id])}"""
    result = f"""
{innertext}

If you have any question, please contact @iwtfll1 and ask for support.
"""
    await update.message.reply_text(result)


def main():
    load_data()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Admin commands
    application.add_handler(CommandHandler("create_product", create_product))
    application.add_handler(CommandHandler("add_card_keys", add_card_keys))
    application.add_handler(CommandHandler("check_inventory", check_inventory))

    # User commands
    application.add_handler(CommandHandler("paysupport", paysupport))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(product_selection))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )

    # Start bot
    application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
