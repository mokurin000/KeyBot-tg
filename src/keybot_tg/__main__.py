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
    Application,
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
    await context.bot.set_my_commands(
        [
            BotCommand("start", "Show the product list"),
            BotCommand("paysupport", "After-pay service"),
        ]
    )
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"product-{name}")]
        for name in products.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Please choose the product you want to purchase:", reply_markup=reply_markup
    )


# Handle product selection
async def product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    product_name = query.data.split("-")[1]
    await query.answer()
    await query.message.reply_text(
        f"How many units of {product_name} would you like to purchase?"
    )
    context.user_data["selected_product"] = product_name


# Handle quantity message
async def quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "selected_product" not in context.user_data:
        await update.message.reply_text("Please select a product first using /start.")
        return

    try:
        quantity = int(update.message.text.strip())
        product_name = context.user_data["selected_product"]

        if quantity < 1:
            raise ValueError("Quantity must be a positive integer.")

        if quantity > len(card_keys[product_name]):
            await update.message.reply_text(
                f"Sorry, only {len(card_keys[product_name])} units of {product_name} are available."
            )
            return

        product = products[product_name]
        title = f"Purchase {product_name} ({quantity} units)"
        description = product["description"]
        payload = f"purchase-{product_name}-{quantity}"
        currency = "XTR"
        prices = [
            LabeledPrice(
                f"{product_name} card key x{quantity}", product["price"] * quantity
            )
        ]

        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency=currency,
            prices=prices,
            start_parameter="card-purchase",
            is_flexible=False,
        )

    except ValueError:
        await update.message.reply_text("Please enter a valid integer quantity.")


# Handle pre-checkout (check payment information)
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    payload_parts = query.invoice_payload.split("-")
    product_name = payload_parts[1]
    quantity = int(payload_parts[2])

    if product_name in card_keys and len(card_keys[product_name]) >= quantity:
        await query.answer(ok=True)
    else:
        await query.answer(
            ok=False, error_message=f"Sorry, insufficient stock for {product_name}."
        )


# Handle successful payment
async def successful_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    charge_id = update.message.successful_payment.telegram_payment_charge_id
    payload_parts = update.message.successful_payment.invoice_payload.split("-")
    product_name = payload_parts[1]
    quantity = int(payload_parts[2])

    payhistory[user_id] = payhistory.get(user_id, []) + [charge_id]
    save_data()

    if product_name in card_keys and len(card_keys[product_name]) >= quantity:
        purchased_keys = card_keys[product_name][:quantity]
        del card_keys[product_name][:quantity]
        save_data()
        key_list = "\n".join(purchased_keys)
        await update.message.reply_text(
            f"Thank you for your purchase! Your card keys are:\n{key_list}\nCharge ID: {charge_id}"
        )

        # Notify admin
        admin_message = f"Successful payment for '{product_name}' by user {user_id}. Charge ID: {charge_id}"
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(admin_id, admin_message)
    else:
        await update.message.reply_text(
            f"Sorry, '{product_name}' is out of stock.\nCharge ID: {charge_id}"
        )

        # Notify admin
        admin_message = f"Out-Of-Stock payment for '{product_name}' by user {user_id}. Charge ID: {charge_id}"
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(admin_id, admin_message)


# Admin command to check the inventory of card keys
async def paysupport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in payhistory:
        innertext = "Sorry, but we found no transition related to you."
    else:
        innertext = f"""Your transitions:
{"\n\n".join(map(lambda s: "order id: " + s, payhistory[user_id]))}"""
    result = f"""
{innertext}

If you have any question, please contact @iwtfll1 and ask for support.
"""
    await update.message.reply_text(result)


def main():
    load_data()

    async def print_username(app: Application):
        print(f"Bot username: @{app.bot.username}")

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(print_username).build()

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

    # Handle user-specified quantities
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_handler)
    )

    # Start bot
    application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
