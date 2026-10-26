# Food Ordering App

A command line ordering application for a fictional snack bar, built as the
Dataquest guided project *Build a Food Ordering App*. The user browses a menu,
adds and removes items, changes quantities, views the cart, and checks out with
sales tax applied.

The brief fixes the data: ten items keyed by SKU, six numbered actions, a sales
tax constant, and a cart that starts empty. What the brief leaves open is how
to hold the money and how to structure the program, and both of those turned
out to matter more than the feature list.

## Running it

```
python3 app.py          # the interactive app
python3 -m unittest -v test_app    # 49 tests
python3 reproduce_float_bug.py     # the evidence behind one design decision
```

No third party packages. Python 3.6 or newer.

```
Your cart
------------------------------------------
Hamburger         2 x   $6.51     $13.02
Milkshake         6 x   $5.99     $35.94
Brownie           6 x   $2.46     $14.76
Fries             2 x   $2.39      $4.78
------------------------------------------
Subtotal                           $68.50
Tax (7%)                            $4.80
Total                              $73.30
```

## The money is stored in integer cents, and that is not stylistic

The project suggests a float for the tax rate, and a float price per item is
the obvious companion. That combination produces bills that are wrong by a
cent, and the mechanism is specific enough to be worth stating exactly rather
than gesturing at floating point in general.

At 7% tax, a subtotal ending in exactly `.50` owes an exact half cent in tax.
A $122.50 subtotal owes $8.575. A half cent is a tie, and any billing system
has to break it in some direction. This one rounds ties up, so the tax is
$8.58 and the total is $131.08.

A float subtotal cannot be relied on to reach that tie at all:

```
exact subtotal        $122.50, so the tax is exactly $8.575
that is a half cent, which is a tie, and ties here round up

float subtotal        122.49999999999998578915
float tax             8.57499999999999928946
no longer a tie, so it rounds down instead

integer total         $131.08
float total           $131.07
```

The float version is not applying a different rounding rule. It never saw a
tie, because `6.51 * 8` and the rest of the sum do not land where decimal
arithmetic says they should. The customer is charged a cent less, and no line
of the code looks wrong.

Measured over 400,000 randomly generated carts against this menu, holding the
rounding rule identical on both sides so that representation is the only
variable:

| | |
|---|---|
| carts tested | 400,000 |
| totals differing by one cent | 21, about 1 in 19,000 |
| carts whose subtotal ends in `.50` | 1.7% |
| share of those that come out wrong | 0.3% |

One in nineteen thousand sounds ignorable until you notice the second
symptom.

### The same cart can cost two different amounts

Floating point addition is not associative, so a float subtotal depends on the
order the items were accumulated, which is the order the customer happened to
add them:

```
cart: {'sku1': 2, 'sku3': 6, 'sku9': 6, 'sku4': 2}
float charges $73.29 for 2 of the 24 orderings, e.g. sku1 then sku3 then sku9 then sku4
float charges $73.30 for 22 of the 24 orderings, e.g. sku1 then sku3 then sku4 then sku9
integer charges $73.30 for all of them
```

Two customers order the same four items at the same prices. One adds the fries
last and is billed $73.29. The other adds them third and is billed $73.30.
Nothing in the code distinguishes them.

Integer addition is exact and associative, so this cannot happen once the
money is held in cents. Prices are stored as `651` rather than `6.51`, every
calculation stays in integers, and a float never enters the program. Dollars
appear only in `format_cents`, at the moment of display.

The smallest cart that reproduces the discrepancy is nine items across five
lines, subtotal $50.50, which the integer version bills at $54.04 and the
float version at $54.03.

`reproduce_float_bug.py` demonstrates all of the above from scratch without
importing the application, so the claim can be checked independently of the
code it justifies. `test_app.py::TestMoneyBug` locks it in as a regression
test: six specific carts, the half cent mechanism asserted rather than
described, and the order dependence checked across all 24 permutations.

### Two smaller money decisions

**Ties round away from zero, not to even.** Python's built in `round` uses
banker's rounding, so `round(2.5)` is `2`. A receipt that charges 2 cents of
tax where the arithmetic says 2.5 invites a reasonable complaint, so
`round_half_up` is written out explicitly in integers.

**The total is defined as subtotal plus tax, never as `subtotal * 1.07`.**
Calculating the total independently of the lines above it lets the printed
figures disagree with the printed total by a cent. Defining it as the sum
makes that impossible, and a test asserts it over several carts.

## The cart logic is separated from the input and output

The canonical shape for this project is a `while` loop that calls `input()`,
mutates a global cart, and prints as it goes. It works, and it cannot be
tested without simulating a user typing.

Every rule about what may go into a cart lives in a pure function that takes a
cart and returns a new one:

```python
def add_item(cart, sku, quantity=1):
    sku = validate_sku(sku)
    quantity = validate_quantity(quantity)
    updated = dict(cart)
    new_quantity = updated.get(sku, 0) + quantity
    if new_quantity > MAX_QUANTITY:
        raise CartError(...)
    updated[sku] = new_quantity
    return updated
```

Returning a new dict rather than mutating the argument means a rejected
operation leaves the caller's cart untouched, which a test checks directly.
Rejections raise `CartError` rather than returning `None`, so a caller cannot
quietly ignore one, and the message is written once instead of at every call
site.

`run()` holds no rules of its own. It reads a number, calls one of those
functions, catches `CartError`, and prints the result. It also takes its input
and output functions as arguments:

```python
def run(read=input, write=print):
```

which is what makes the whole interactive loop testable. The suite drives it
by handing it a list of keystrokes and reading back what it printed:

```python
def test_remove_from_empty_cart_skips_the_prompt(self):
    # If the loop asked for a SKU here, the next keystroke would be eaten
    # and this test would end up with sku1 in the cart.
    cart, text = self.drive(["2", "1", "sku1", "1", "5"])
    self.assertEqual(cart, {"sku1": 1})
    self.assertIn("empty", text)
```

The fake keyboard raises `EOFError` when it runs out, which is what a real
terminal does at the end of piped input, so the loop's end of input handling
is exercised rather than mocked away.

## Input validation

Hostile input for a program like this is mostly typos, and each one has a
defined answer rather than a traceback:

| Input | Result |
|---|---|
| `sku11`, `hamburger`, empty | rejected, menu has no such SKU |
| `SKU1 ` with case and spaces | accepted, normalised to `sku1` |
| `two`, `3.5`, `1e3`, empty | rejected, not a whole number |
| `0` on an add | rejected, minimum is 1 |
| `0` on a quantity change | accepted, removes the line |
| `-1` | rejected |
| `True` | rejected, even though `bool` subclasses `int` |
| more than 99 of one item | rejected, a typo should not become 1,000 burgers |
| removing an item not in the cart | reported, loop continues |
| checkout with an empty cart | refused, loop continues |
| end of input at any prompt | exits cleanly |

The boolean case is the kind of thing that only shows up when you write the
test: `int(True)` is `1`, so a bare `int()` conversion would silently accept
`True` as a quantity of one.

## Tests

49 tests across seven classes:

- `TestValidation` the SKU and quantity rules in isolation
- `TestCartRules` add, remove, change, and the no mutation guarantee
- `TestMoney` formatting, half up rounding, lines summing to the total
- `TestMoneyBug` the regression tests described above
- `TestRendering` menu, actions, cart, and receipt output
- `TestInteractiveLoop` the full loop driven by scripted keystrokes
- `TestMenuData` the menu matches the brief, prices are integers

```
Ran 49 tests in 0.004s

OK
```

## Files

| File | Contents |
|---|---|
| `app.py` | the application: data, money, cart rules, rendering, loop |
| `test_app.py` | the test suite |
| `reproduce_float_bug.py` | standalone evidence for the integer cents decision |

## What I would change for a real deployment

The cart lives in memory for one session, which is all the brief asks for. A
real ordering system needs the cart persisted per user, the menu loaded from a
data source rather than a literal, and the tax rate resolved by jurisdiction
rather than fixed at 7%. The integer cents decision becomes more important
there, not less, because a cent of drift per order compounds across a day of
them and shows up in a reconciliation nobody wants to do.
