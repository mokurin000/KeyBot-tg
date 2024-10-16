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


# Admin command to create a product with multi-line input
async def create_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        # Split the message into lines
        lines = update.message.text.split("\n")

        if len(lines) < 4:  # Command + price + name + at least one description line
            raise ValueError("Insufficient arguments provided.")

        # Extract price, name, and description
        try:
            price = int(lines[1].strip())
        except ValueError:
            await update.message.reply_text("Price must be an integer.")
            return

        name = lines[2].strip()
        description = "\n".join(line.strip() for line in lines[3:])

        if not name:
            await update.message.reply_text("Product name cannot be empty.")
            return

        if not description:
            await update.message.reply_text("Product description cannot be empty.")
            return

        if name in products:
            await update.message.reply_text(f"Product '{name}' already exists.")
            return

        products[name] = {"description": description, "price": price}
        card_keys[name] = []
        save_data()
        await update.message.reply_text(f"Product '{name}' created successfully!")
    except IndexError:
        await update.message.reply_text(
            "Please use the following format:\n"
            "/create_product\n<price>\n<name>\n<description... (multi-lines supported)>"
        )
    except ValueError as ve:
        await update.message.reply_text(str(ve))


# Admin command to add card keys to a product
async def add_card_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        call_lines = update.message.text.split("\n")
        if len(call_lines) < 2:
            raise ValueError("Insufficient arguments provided.")

        product_line = call_lines[0]
        if not product_line.startswith("/add_card_keys"):
            raise ValueError("Invalid command format.")

        product_name = product_line.split(maxsplit=1)[1].strip()
        new_keys = [line.strip() for line in call_lines[1:] if line.strip()]

        if not new_keys:
            await update.message.reply_text("No card keys provided to add.")
            return

        if product_name in card_keys:
            card_keys[product_name].extend(new_keys)
            save_data()
            await update.message.reply_text(
                f"Added {len(new_keys)} card key(s) to product '{product_name}'."
            )
        else:
            await update.message.reply_text("Product not found.")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Please use the following format:\n"
            "/add_card_keys <product_name>\n<key1>\n<key2>\n..."
        )


# Admin command to check the inventory of card keys
async def check_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not card_keys:
        inventory = "No products available."
    else:
        inventory = "\n".join(
            [f"{k}: {len(v)} key(s) available" for k, v in card_keys.items()]
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
    if not products:
        await update.message.reply_text(
            "No products available at the moment. Please check back later."
        )
        return

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
    product_name = query.data.split("-", 1)[1]
    await query.answer()
    await query.message.reply_text(
        f"How many units of '{product_name}' would you like to purchase?",
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

        available = len(card_keys.get(product_name, []))
        if quantity > available:
            await update.message.reply_text(
                f"Sorry, only {available} unit(s) of '{product_name}' are available."
            )
            return

        product = products[product_name]
        title = f"Purchase {product_name} ({quantity} unit{'s' if quantity >1 else ''})"
        description = product["description"]
        payload = f"purchase-{product_name}-{quantity}"
        currency = "XTR"
        prices = [
            LabeledPrice(
                f"{product_name} card key x{quantity}",
                product["price"] * quantity * 100,  # Assuming price is in cents
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
    if len(payload_parts) < 3:
        await query.answer(ok=False, error_message="Invalid payload.")
        return

    product_name = payload_parts[1]
    try:
        quantity = int(payload_parts[2])
    except ValueError:
        await query.answer(ok=False, error_message="Invalid quantity.")
        return

    if product_name in card_keys and len(card_keys[product_name]) >= quantity:
        await query.answer(ok=True)
    else:
        await query.answer(
            ok=False, error_message=f"Sorry, insufficient stock for '{product_name}'."
        )


# Handle successful payment
async def successful_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    charge_id = update.message.successful_payment.telegram_payment_charge_id
    payload_parts = update.message.successful_payment.invoice_payload.split("-")
    if len(payload_parts) < 3:
        await update.message.reply_text("Invalid payment payload.")
        return

    product_name = payload_parts[1]
    try:
        quantity = int(payload_parts[2])
    except ValueError:
        await update.message.reply_text("Invalid purchase quantity.")
        return

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
        innertext = "Sorry, but we found no transactions related to you."
    else:
        innertext = f"""Your transactions:
{"".join(map(lambda s: f"• Order ID: {s}\n", payhistory[user_id]))}"""
    result = f"""
{innertext}

If you have any questions, please contact @iwtfll1 and ask for support.
"""
    await update.message.reply_text(result)


# **New Admin Command to Remove Products**
REMOVE_PRODUCT_PREFIX = "remove_product"
CONFIRM_REMOVE_PREFIX = "confirm_remove"


# Admin command to initiate product removal
async def remove_product_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not products:
        await update.message.reply_text("No products available to remove.")
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"{REMOVE_PRODUCT_PREFIX}-{name}")]
        for name in products.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select the product you want to remove:", reply_markup=reply_markup
    )


# Handler for remove product button clicks
async def remove_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # **Admin Permission Check**
    if user_id not in ADMIN_IDS:
        await query.answer(
            "You do not have permission to perform this action.", show_alert=True
        )
        return

    product_name = query.data.split(f"{REMOVE_PRODUCT_PREFIX}-", 1)[1]
    await query.answer()
    await query.message.reply_text(
        f"Are you sure you want to remove the product '{product_name}'?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes",
                        callback_data=f"{CONFIRM_REMOVE_PREFIX}-yes-{product_name}",
                    ),
                    InlineKeyboardButton(
                        "No", callback_data=f"{CONFIRM_REMOVE_PREFIX}-no-{product_name}"
                    ),
                ]
            ]
        ),
    )


# Handler for confirmation callbacks
async def confirm_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # **Admin Permission Check**
    if user_id not in ADMIN_IDS:
        await query.answer(
            "You do not have permission to perform this action.", show_alert=True
        )
        return

    await query.answer()
    data_parts = query.data.split("-")
    if len(data_parts) < 3:
        await query.message.reply_text("Invalid confirmation data.")
        return

    action = data_parts[1]
    product_name = "-".join(data_parts[2:])  # In case product name contains '-'

    if action.lower() == "yes":
        if product_name in products:
            del products[product_name]
        if product_name in card_keys:
            del card_keys[product_name]
        # Optionally, remove related payhistory if necessary
        # Here, assuming payhistory doesn't need to be cleaned up as it's user-specific

        save_data()
        await query.message.reply_text(f"Product '{product_name}' has been removed.")

        # Notify admins about the removal
        admin_message = f"Product '{product_name}' has been removed by user {user_id}."
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                await context.bot.send_message(admin_id, admin_message)
    else:
        await query.message.reply_text("Product removal canceled.")


def main():
    load_data()

    async def print_username(app: Application):
        print(f"Bot username: @{app.bot.username}")

    application = (
        ApplicationBuilder().token(BOT_TOKEN).post_init(print_username).build()
    )

    # Admin commands
    application.add_handler(CommandHandler("create_product", create_product))
    application.add_handler(CommandHandler("add_card_keys", add_card_keys))
    application.add_handler(CommandHandler("check_inventory", check_inventory))
    application.add_handler(CommandHandler("remove_product", remove_product_command))
    application.add_handler(
        CallbackQueryHandler(
            remove_product_selection, pattern=f"^{REMOVE_PRODUCT_PREFIX}-"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            confirm_remove_product, pattern=f"^{CONFIRM_REMOVE_PREFIX}-"
        )
    )

    # User commands
    application.add_handler(CommandHandler("paysupport", paysupport))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(product_selection, pattern="^product-")
    )
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
