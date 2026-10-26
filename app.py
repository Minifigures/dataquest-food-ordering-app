"""Snack Shack: an interactive food ordering application.

Dataquest guided project, Build a Food Ordering App.

Two design decisions drive the structure of this module, and both exist
because the obvious implementation is subtly wrong.

1. Money is stored and calculated in integer cents, never floats.
   At a 7% tax, a subtotal ending in exactly .50 owes an exact half cent in
   tax, which is a tie that billing has to break. This app breaks ties
   upward. Summing the same prices as floats does not reliably arrive at the
   tie: $68.50 can accumulate to 68.49999999999998, whose tax is
   4.79499999999999904 rather than 4.795, so it rounds down and the customer
   is charged a cent less. Over 400,000 random carts the two disagree on 21,
   about 1 in 19,000. Worse, the float result depends on the order the items
   were added: 2 of the 24 orderings of one cart charge $73.29 and the other
   22 charge $73.30. See `test_app.py::TestMoneyBug`.

2. Cart logic is separated from input and output.
   Every rule about what may go in a cart lives in a pure function that takes
   a cart and returns a new one. The functions that read from the keyboard and
   write to the screen do nothing else. This means the rules can be tested
   directly, without simulating a user typing.
"""

RESTAURANT_NAME = "The Snack Shack"

# Prices in integer cents. $6.51 is 651, and no float ever touches the money.
MENU = {
    "sku1":  {"name": "Hamburger",      "price_cents":  651},
    "sku2":  {"name": "Cheeseburger",   "price_cents":  775},
    "sku3":  {"name": "Milkshake",      "price_cents":  599},
    "sku4":  {"name": "Fries",          "price_cents":  239},
    "sku5":  {"name": "Sub",            "price_cents":  587},
    "sku6":  {"name": "Ice Cream",      "price_cents":  155},
    "sku7":  {"name": "Fountain Drink", "price_cents":  345},
    "sku8":  {"name": "Cookie",         "price_cents":  315},
    "sku9":  {"name": "Brownie",        "price_cents":  246},
    "sku10": {"name": "Sauce",          "price_cents":   75},
}

# Tax as a fraction expressed in integers too: 7% is 7 per 100.
TAX_NUMERATOR = 7
TAX_DENOMINATOR = 100

MAX_QUANTITY = 99  # a guard against a typo turning into a thousand burgers

ACTIONS = {
    1: "Add an item to the cart",
    2: "Remove an item from the cart",
    3: "Change an item's quantity",
    4: "View the cart",
    5: "Checkout",
    6: "Exit",
}


class CartError(Exception):
    """Raised when a requested cart change is not allowed.

    Carrying the reason as an exception rather than returning None means a
    caller cannot accidentally ignore a failure, and the message is written
    once rather than at every call site.
    """


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def format_cents(cents):
    """Render integer cents as a dollar string.

    Negative values are handled explicitly because -5 // 100 is -1 in Python,
    not 0, so the naive version prints -$1.95 for -5 cents.
    """
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s$%d.%02d" % (sign, cents // 100, cents % 100)


def round_half_up(numerator, denominator):
    """Divide and round halves away from zero, as retail billing does.

    Python's round() uses banker's rounding, so round(2.5) is 2 and round(3.5)
    is 4. A customer charged 2 cents on a 2.5 cent tax would reasonably query
    the receipt, so this rounds 2.5 up to 3.
    """
    if denominator == 0:
        raise ZeroDivisionError("denominator must not be zero")
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    numerator, denominator = abs(numerator), abs(denominator)
    return sign * ((2 * numerator + denominator) // (2 * denominator))


def subtotal_cents(cart):
    """Sum of price times quantity for every line, in cents."""
    return sum(MENU[sku]["price_cents"] * qty for sku, qty in cart.items())


def tax_cents(subtotal):
    """Tax on a subtotal, rounded half up to the nearest cent."""
    return round_half_up(subtotal * TAX_NUMERATOR, TAX_DENOMINATOR)


def order_totals(cart):
    """Return (subtotal, tax, total) in cents.

    The total is subtotal plus tax, not a separate calculation of
    subtotal * 1.07, so the printed lines always add up to the printed total.
    """
    subtotal = subtotal_cents(cart)
    tax = tax_cents(subtotal)
    return subtotal, tax, subtotal + tax


# ---------------------------------------------------------------------------
# Cart rules, all pure: they take a cart and return a new one
# ---------------------------------------------------------------------------

def validate_sku(sku):
    """Return the canonical SKU, or raise CartError."""
    key = str(sku).strip().lower()
    if key not in MENU:
        raise CartError("There is no item with SKU %r on the menu." % sku)
    return key


def validate_quantity(quantity, allow_zero=False):
    """Return quantity as an int, or raise CartError.

    Accepts a string so the caller does not have to convert before validating,
    and rejects floats outright: 2.5 hamburgers is a typo, not an order.
    """
    if isinstance(quantity, bool) or isinstance(quantity, float):
        raise CartError("Quantity must be a whole number.")
    try:
        value = int(str(quantity).strip())
    except (TypeError, ValueError):
        raise CartError("%r is not a whole number." % quantity)
    low = 0 if allow_zero else 1
    if value < low:
        raise CartError("Quantity must be at least %d." % low)
    if value > MAX_QUANTITY:
        raise CartError("Quantity may not exceed %d per item." % MAX_QUANTITY)
    return value


def add_item(cart, sku, quantity=1):
    """Add quantity of sku, accumulating onto any quantity already there."""
    sku = validate_sku(sku)
    quantity = validate_quantity(quantity)
    updated = dict(cart)
    new_quantity = updated.get(sku, 0) + quantity
    if new_quantity > MAX_QUANTITY:
        raise CartError(
            "That would make %d of %s, and the limit is %d."
            % (new_quantity, MENU[sku]["name"], MAX_QUANTITY))
    updated[sku] = new_quantity
    return updated


def remove_item(cart, sku):
    """Remove a line entirely."""
    sku = validate_sku(sku)
    if sku not in cart:
        raise CartError("%s is not in your cart." % MENU[sku]["name"])
    updated = dict(cart)
    del updated[sku]
    return updated


def set_quantity(cart, sku, quantity):
    """Set a line to an exact quantity. Zero removes the line."""
    sku = validate_sku(sku)
    if sku not in cart:
        raise CartError("%s is not in your cart." % MENU[sku]["name"])
    quantity = validate_quantity(quantity, allow_zero=True)
    updated = dict(cart)
    if quantity == 0:
        del updated[sku]
    else:
        updated[sku] = quantity
    return updated


def clear_cart(cart):
    """Empty the cart."""
    return {}


# ---------------------------------------------------------------------------
# Rendering, which returns strings rather than printing them
# ---------------------------------------------------------------------------

def render_menu():
    lines = ["", "%s menu" % RESTAURANT_NAME, "-" * 34]
    for sku, item in MENU.items():
        lines.append("%-6s %-16s %8s" % (sku, item["name"],
                                         format_cents(item["price_cents"])))
    return "\n".join(lines)


def render_actions():
    lines = ["", "What would you like to do?"]
    for number, label in ACTIONS.items():
        lines.append("  (%d) %s" % (number, label))
    return "\n".join(lines)


def render_cart(cart):
    if not cart:
        return "\nYour cart is empty."
    lines = ["", "Your cart", "-" * 42]
    for sku, quantity in cart.items():
        item = MENU[sku]
        line_total = item["price_cents"] * quantity
        lines.append("%-16s %2d x %7s %10s"
                     % (item["name"], quantity,
                        format_cents(item["price_cents"]),
                        format_cents(line_total)))
    subtotal, tax, total = order_totals(cart)
    lines.append("-" * 42)
    lines.append("%-26s %14s" % ("Subtotal", format_cents(subtotal)))
    lines.append("%-26s %14s" % ("Tax (%d%%)" % TAX_NUMERATOR, format_cents(tax)))
    lines.append("%-26s %14s" % ("Total", format_cents(total)))
    return "\n".join(lines)


def render_receipt(cart):
    return "\n".join([render_cart(cart), "", "Thank you for ordering from %s."
                      % RESTAURANT_NAME])


# ---------------------------------------------------------------------------
# Input and output, kept apart from everything above
# ---------------------------------------------------------------------------

def ask(prompt, read=input, write=print):
    """Read one line. Returns None if the user interrupts or input ends.

    read and write are injectable so the loop can be driven by a test or a
    script instead of a keyboard.
    """
    try:
        return read(prompt)
    except (EOFError, KeyboardInterrupt):
        write("")
        return None


def run(read=input, write=print):
    """The application loop.

    Holds no cart rules of its own: it reads a choice, calls one of the pure
    functions above, and prints whatever came back. Every CartError becomes a
    message rather than a traceback.
    """
    cart = {}
    write("\nWelcome to %s!" % RESTAURANT_NAME)
    write(render_menu())

    while True:
        write(render_actions())
        choice = ask("Enter a number: ", read, write)
        if choice is None:
            write("\nGoodbye.")
            return cart

        try:
            action = int(choice.strip())
        except (AttributeError, ValueError):
            write("Please enter one of the numbers listed.")
            continue
        if action not in ACTIONS:
            write("Please enter one of the numbers listed.")
            continue

        if action == 6:
            write("\nGoodbye.")
            return cart

        if action == 5:
            if not cart:
                write("\nThere is nothing to check out. Add an item first.")
                continue
            write(render_receipt(cart))
            return cart

        if action == 4:
            write(render_cart(cart))
            continue

        if action == 1:
            write(render_menu())
            sku = ask("SKU to add: ", read, write)
            quantity = ask("Quantity: ", read, write)
            if sku is None or quantity is None:
                write("\nGoodbye.")
                return cart
            try:
                cart = add_item(cart, sku, quantity)
            except CartError as problem:
                write(str(problem))
            else:
                write("Added.")
            continue

        if action == 2:
            write(render_cart(cart))
            if not cart:
                continue
            sku = ask("SKU to remove: ", read, write)
            if sku is None:
                write("\nGoodbye.")
                return cart
            try:
                cart = remove_item(cart, sku)
            except CartError as problem:
                write(str(problem))
            else:
                write("Removed.")
            continue

        if action == 3:
            write(render_cart(cart))
            if not cart:
                continue
            sku = ask("SKU to change: ", read, write)
            quantity = ask("New quantity (0 removes it): ", read, write)
            if sku is None or quantity is None:
                write("\nGoodbye.")
                return cart
            try:
                cart = set_quantity(cart, sku, quantity)
            except CartError as problem:
                write(str(problem))
            else:
                write("Updated.")
            continue


if __name__ == "__main__":
    run()
