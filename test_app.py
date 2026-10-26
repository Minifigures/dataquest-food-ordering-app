"""Tests for the Snack Shack ordering app.

Run with: python3 -m unittest -v test_app

The suite is divided into three parts. The first covers the cart rules, which
is what any guided project asks for. The second covers money, including a
regression test built from carts that the obvious float implementation gets
wrong by a cent. The third drives the whole interactive loop by feeding it a
list of keystrokes, which is only possible because run() takes its read and
write functions as arguments.
"""

import itertools
import math
import unittest

import app
from app import CartError


class TestValidation(unittest.TestCase):

    def test_sku_is_normalised(self):
        self.assertEqual(app.validate_sku(" SKU1 "), "sku1")

    def test_unknown_sku_rejected(self):
        with self.assertRaises(CartError):
            app.validate_sku("sku11")
        with self.assertRaises(CartError):
            app.validate_sku("hamburger")
        with self.assertRaises(CartError):
            app.validate_sku("")

    def test_quantity_accepts_digit_strings(self):
        self.assertEqual(app.validate_quantity("3"), 3)
        self.assertEqual(app.validate_quantity(" 12 "), 12)

    def test_quantity_rejects_nonsense(self):
        for bad in ["", "two", "3.5", "-1", "0", "1e3", None, 2.0]:
            with self.subTest(bad=bad):
                with self.assertRaises(CartError):
                    app.validate_quantity(bad)

    def test_quantity_rejects_booleans(self):
        # True would otherwise sneak through as 1, since bool subclasses int.
        with self.assertRaises(CartError):
            app.validate_quantity(True)

    def test_quantity_cap_enforced(self):
        self.assertEqual(app.validate_quantity(app.MAX_QUANTITY),
                         app.MAX_QUANTITY)
        with self.assertRaises(CartError):
            app.validate_quantity(app.MAX_QUANTITY + 1)

    def test_zero_allowed_only_when_asked(self):
        self.assertEqual(app.validate_quantity("0", allow_zero=True), 0)
        with self.assertRaises(CartError):
            app.validate_quantity("0")


class TestCartRules(unittest.TestCase):

    def test_add_returns_a_new_cart(self):
        original = {}
        result = app.add_item(original, "sku1", 2)
        self.assertEqual(result, {"sku1": 2})
        self.assertEqual(original, {}, "the caller's cart must not be mutated")

    def test_add_accumulates(self):
        cart = app.add_item({}, "sku1", 2)
        cart = app.add_item(cart, "sku1", 3)
        self.assertEqual(cart, {"sku1": 5})

    def test_add_defaults_to_one(self):
        self.assertEqual(app.add_item({}, "sku4"), {"sku4": 1})

    def test_add_respects_the_cap_across_calls(self):
        cart = app.add_item({}, "sku1", 98)
        with self.assertRaises(CartError):
            app.add_item(cart, "sku1", 2)
        self.assertEqual(cart, {"sku1": 98}, "a rejected add changes nothing")

    def test_remove_deletes_the_line(self):
        cart = app.add_item(app.add_item({}, "sku1", 1), "sku2", 1)
        self.assertEqual(app.remove_item(cart, "sku1"), {"sku2": 1})

    def test_remove_absent_item_raises(self):
        with self.assertRaises(CartError):
            app.remove_item({"sku1": 1}, "sku2")

    def test_set_quantity_replaces_rather_than_adds(self):
        cart = app.add_item({}, "sku1", 5)
        self.assertEqual(app.set_quantity(cart, "sku1", 2), {"sku1": 2})

    def test_set_quantity_zero_removes(self):
        cart = app.add_item({}, "sku1", 5)
        self.assertEqual(app.set_quantity(cart, "sku1", 0), {})

    def test_set_quantity_on_absent_item_raises(self):
        with self.assertRaises(CartError):
            app.set_quantity({}, "sku1", 1)

    def test_clear(self):
        self.assertEqual(app.clear_cart({"sku1": 1}), {})


class TestMoney(unittest.TestCase):

    def test_format_cents(self):
        cases = [(0, "$0.00"), (5, "$0.05"), (75, "$0.75"), (100, "$1.00"),
                 (651, "$6.51"), (123456, "$1234.56"), (-5, "-$0.05")]
        for cents, expected in cases:
            with self.subTest(cents=cents):
                self.assertEqual(app.format_cents(cents), expected)

    def test_round_half_up_goes_up_where_round_goes_down(self):
        # round(2.5) is 2 in Python. Billing should charge 3.
        self.assertEqual(app.round_half_up(5, 2), 3)
        self.assertEqual(app.round_half_up(7, 2), 4)
        self.assertEqual(app.round_half_up(1, 3), 0)
        self.assertEqual(app.round_half_up(2, 3), 1)

    def test_empty_cart_totals_zero(self):
        self.assertEqual(app.order_totals({}), (0, 0, 0))

    def test_single_item_totals(self):
        subtotal, tax, total = app.order_totals({"sku1": 1})
        self.assertEqual(subtotal, 651)
        self.assertEqual(tax, 46)          # 651 * 7 / 100 = 45.57, rounds to 46
        self.assertEqual(total, 697)
        self.assertEqual(app.format_cents(total), "$6.97")

    def test_printed_lines_always_sum_to_the_printed_total(self):
        # A separate subtotal * 1.07 could disagree with subtotal + tax by a
        # cent. Here the total is defined as the sum, so it cannot.
        for cart in [{"sku1": 1}, {"sku10": 7}, {"sku3": 2, "sku4": 3},
                     {"sku%d" % n: n for n in range(1, 11)}]:
            with self.subTest(cart=cart):
                subtotal, tax, total = app.order_totals(cart)
                self.assertEqual(subtotal + tax, total)

    def test_quantity_scales_linearly(self):
        one = app.subtotal_cents({"sku2": 1})
        ten = app.subtotal_cents({"sku2": 10})
        self.assertEqual(ten, one * 10)


class TestMoneyBug(unittest.TestCase):
    """Regression tests for the float arithmetic this app deliberately avoids.

    The mechanism is narrow and worth stating precisely rather than waving at
    floats in general. Tax here is 7%, so the tax on a subtotal is an exact
    half cent whenever the subtotal ends in exactly .50: $122.50 owes
    $8.575. A half cent is a tie, and any billing system has to pick a
    direction. This app rounds ties up.

    A float subtotal cannot be relied upon to arrive at the tie at all. Summing
    the same prices as floats can land on 122.49999999999998578915, whose tax
    is 8.57499999999999928946, which is no longer a tie and rounds down. The
    float version therefore charges a cent less, not because it chose a
    different rounding rule but because it never saw the tie.

    Measured over 400,000 random carts against this menu, the two disagree on
    21 of them, about 1 in 19,000. Only carts whose subtotal ends in .50 can be
    affected (1.76% of carts), and 0.3% of those come out wrong.
    """

    # cart, exact total in cents, what float accumulation charges instead
    KNOWN_BAD = [
        ({"sku1": 2, "sku3": 6, "sku9": 6, "sku4": 2}, 7330, 7329),
        ({"sku1": 8, "sku9": 8, "sku2": 3, "sku5": 2, "sku8": 5}, 13108, 13107),
        ({"sku1": 7, "sku2": 8, "sku6": 6, "sku8": 8,
          "sku3": 2, "sku7": 1}, 16853, 16852),
        ({"sku2": 8, "sku1": 4, "sku3": 9, "sku7": 8,
          "sku8": 8, "sku10": 9}, 21561, 21560),
        ({"sku9": 1, "sku1": 9, "sku6": 1, "sku2": 9,
          "sku4": 5, "sku8": 8}, 18137, 18136),
        # The smallest cart that reproduces it: 9 items, subtotal $50.50.
        ({"sku1": 2, "sku2": 2, "sku3": 3, "sku6": 1, "sku9": 1}, 5404, 5403),
    ]

    @staticmethod
    def float_total(pairs):
        """The implementation a guided project would naturally produce.

        Takes an ordered sequence rather than a dict, because the result
        depends on the order of accumulation, which is the point of
        test_the_same_cart_can_total_two_different_amounts below.
        """
        dollars = {sku: item["price_cents"] / 100.0
                   for sku, item in app.MENU.items()}
        subtotal = 0.0
        for sku, quantity in pairs:
            subtotal += dollars[sku] * quantity
        tax = subtotal * (app.TAX_NUMERATOR / 100.0)
        # Half up applied to the float, the way a careful beginner would.
        return int(math.floor(subtotal * 100 + 0.5)
                   + math.floor(tax * 100 + 0.5))

    def test_integer_version_is_correct_where_float_is_not(self):
        for cart, exact, float_answer in self.KNOWN_BAD:
            with self.subTest(cart=cart):
                self.assertNotEqual(
                    exact, float_answer,
                    "this case is only interesting if they differ")
                self.assertEqual(
                    self.float_total(list(cart.items())), float_answer,
                    "the float bug should still reproduce")
                _, _, total = app.order_totals(cart)
                self.assertEqual(total, exact,
                                 "the integer version must get it right")

    def test_every_failing_cart_sits_on_an_exact_half_cent(self):
        """The mechanism claimed in the docstring, asserted rather than told."""
        for cart, _, _ in self.KNOWN_BAD:
            with self.subTest(cart=cart):
                subtotal = app.subtotal_cents(cart)
                self.assertEqual(
                    subtotal % 100, 50,
                    "a subtotal not ending in .50 cannot produce a tie")
                self.assertEqual((subtotal * app.TAX_NUMERATOR) % 100, 50,
                                 "the tax should be an exact half cent")

    def test_the_documented_example_in_full(self):
        cart = {"sku1": 2, "sku3": 6, "sku9": 6, "sku4": 2}
        subtotal, tax, total = app.order_totals(cart)
        self.assertEqual(app.format_cents(subtotal), "$68.50")
        self.assertEqual(app.format_cents(tax), "$4.80")   # 4.795 rounds up
        self.assertEqual(app.format_cents(total), "$73.30")
        self.assertEqual(subtotal + tax, total)

    def test_the_same_cart_can_total_two_different_amounts(self):
        """Float accumulation makes the bill depend on the order of adding.

        Two of the 24 orderings of this cart reach 68.49999999999998 and
        charge a cent less than the other 22. A customer who adds fries last
        pays a different price than one who adds them third.
        """
        cart = {"sku1": 2, "sku3": 6, "sku9": 6, "sku4": 2}
        totals = set()
        for ordering in itertools.permutations(cart.items()):
            totals.add(self.float_total(ordering))
        self.assertEqual(
            totals, {7329, 7330},
            "the float version should give two different answers")

        # The integer version cannot do this: addition of ints is exact, so
        # every ordering gives the same number.
        integer_totals = set()
        for ordering in itertools.permutations(cart.items()):
            integer_totals.add(app.order_totals(dict(ordering))[2])
        self.assertEqual(integer_totals, {7330},
                         "integer cents must be order independent")

    def test_a_tenth_of_a_cent_never_appears(self):
        # Every total is an integer number of cents by construction, so there
        # is no value that formats as one thing and sums as another.
        for quantity in range(1, 100):
            subtotal, tax, total = app.order_totals({"sku10": quantity})
            self.assertIsInstance(total, int)
            self.assertEqual(total, subtotal + tax)


class TestRendering(unittest.TestCase):

    def test_menu_lists_every_item(self):
        text = app.render_menu()
        for item in app.MENU.values():
            self.assertIn(item["name"], text)
        self.assertIn("$6.51", text)

    def test_actions_lists_every_action(self):
        text = app.render_actions()
        for number in app.ACTIONS:
            self.assertIn("(%d)" % number, text)

    def test_empty_cart_says_so(self):
        self.assertIn("empty", app.render_cart({}))

    def test_cart_shows_lines_and_totals(self):
        text = app.render_cart({"sku1": 2})
        self.assertIn("Hamburger", text)
        self.assertIn("$13.02", text)     # 2 x 6.51 line total
        self.assertIn("Subtotal", text)
        self.assertIn("Total", text)

    def test_no_em_dashes_anywhere_in_output(self):
        text = "\n".join([app.render_menu(), app.render_actions(),
                          app.render_cart({"sku1": 1}),
                          app.render_receipt({"sku1": 1})])
        self.assertNotIn(chr(0x2014), text)  # the em dash


class Keyboard:
    """A stand-in for input() that reads from a list, plus a capture for print.

    Raises EOFError when the script runs out, which is exactly what a real
    terminal does at the end of piped input, so the loop's EOF handling is
    exercised rather than mocked away.
    """

    def __init__(self, keystrokes):
        self.keystrokes = list(keystrokes)
        self.output = []

    def read(self, prompt=""):
        if not self.keystrokes:
            raise EOFError
        return self.keystrokes.pop(0)

    def write(self, *parts):
        self.output.append(" ".join(str(p) for p in parts))

    @property
    def text(self):
        return "\n".join(self.output)


class TestInteractiveLoop(unittest.TestCase):

    def drive(self, keystrokes):
        kb = Keyboard(keystrokes)
        cart = app.run(read=kb.read, write=kb.write)
        return cart, kb.text

    def test_exit_immediately(self):
        cart, text = self.drive(["6"])
        self.assertEqual(cart, {})
        self.assertIn("Goodbye", text)

    def test_add_then_checkout(self):
        cart, text = self.drive(["1", "sku1", "2", "5"])
        self.assertEqual(cart, {"sku1": 2})
        self.assertIn("Thank you", text)
        self.assertIn("$13.02", text)

    def test_checkout_on_empty_cart_is_refused_not_crashed(self):
        cart, text = self.drive(["5", "6"])
        self.assertEqual(cart, {})
        self.assertIn("nothing to check out", text)

    def test_bad_menu_choice_reprompts(self):
        cart, text = self.drive(["99", "banana", "", "6"])
        self.assertEqual(cart, {})
        self.assertEqual(text.count("Please enter one of the numbers listed."), 3)

    def test_bad_sku_reported_and_loop_survives(self):
        cart, text = self.drive(["1", "sku99", "1", "1", "sku1", "1", "5"])
        self.assertEqual(cart, {"sku1": 1})
        self.assertIn("no item with SKU", text)

    def test_bad_quantity_reported_and_loop_survives(self):
        cart, text = self.drive(["1", "sku1", "many", "1", "sku1", "1", "5"])
        self.assertEqual(cart, {"sku1": 1})
        self.assertIn("not a whole number", text)

    def test_remove_flow(self):
        cart, _ = self.drive(["1", "sku1", "1", "1", "sku2", "1",
                              "2", "sku1", "5"])
        self.assertEqual(cart, {"sku2": 1})

    def test_remove_from_empty_cart_skips_the_prompt(self):
        # If the loop asked for a SKU here, the next keystroke would be eaten
        # and this test would end up with sku1 in the cart.
        cart, text = self.drive(["2", "1", "sku1", "1", "5"])
        self.assertEqual(cart, {"sku1": 1})
        self.assertIn("empty", text)

    def test_modify_quantity_flow(self):
        cart, _ = self.drive(["1", "sku3", "1", "3", "sku3", "4", "5"])
        self.assertEqual(cart, {"sku3": 4})

    def test_modify_to_zero_removes(self):
        cart, _ = self.drive(["1", "sku3", "1", "3", "sku3", "0", "6"])
        self.assertEqual(cart, {})

    def test_view_cart_does_not_change_it(self):
        cart, text = self.drive(["1", "sku1", "1", "4", "6"])
        self.assertEqual(cart, {"sku1": 1})
        self.assertIn("Hamburger", text)

    def test_running_out_of_input_exits_cleanly(self):
        cart, text = self.drive(["1", "sku1", "1"])
        self.assertEqual(cart, {"sku1": 1})
        self.assertIn("Goodbye", text)

    def test_receipt_totals_match_the_cart_functions(self):
        cart, text = self.drive(["1", "sku2", "3", "1", "sku4", "2", "5"])
        subtotal, tax, total = app.order_totals(cart)
        self.assertIn(app.format_cents(subtotal), text)
        self.assertIn(app.format_cents(tax), text)
        self.assertIn(app.format_cents(total), text)


class TestMenuData(unittest.TestCase):
    """The brief fixes the menu, so a typo in a price should fail loudly."""

    EXPECTED = {
        "sku1": ("Hamburger", 651), "sku2": ("Cheeseburger", 775),
        "sku3": ("Milkshake", 599), "sku4": ("Fries", 239),
        "sku5": ("Sub", 587), "sku6": ("Ice Cream", 155),
        "sku7": ("Fountain Drink", 345), "sku8": ("Cookie", 315),
        "sku9": ("Brownie", 246), "sku10": ("Sauce", 75),
    }

    def test_menu_matches_the_brief(self):
        self.assertEqual(set(app.MENU), set(self.EXPECTED))
        for sku, (name, cents) in self.EXPECTED.items():
            with self.subTest(sku=sku):
                self.assertEqual(app.MENU[sku]["name"], name)
                self.assertEqual(app.MENU[sku]["price_cents"], cents)

    def test_prices_are_integers_not_floats(self):
        for sku, item in app.MENU.items():
            with self.subTest(sku=sku):
                self.assertIsInstance(item["price_cents"], int)

    def test_six_actions(self):
        self.assertEqual(sorted(app.ACTIONS), [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main(verbosity=2)
