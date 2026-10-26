"""Standalone evidence for the design decision in app.py.

Run with: python3 reproduce_float_bug.py

Nothing here imports app.py. It reimplements both approaches from scratch so
the comparison does not depend on the thing being defended, and so a reader
can check the claim without reading the application at all.

Both sides use the same rounding rule, ties upward. The only difference is
whether money is held as integer cents or as floating point dollars, so any
disagreement is caused by representation alone and not by a choice of rule.
"""

import itertools
import math
import random

PRICES_CENTS = {
    "sku1": 651, "sku2": 775, "sku3": 599, "sku4": 239, "sku5": 587,
    "sku6": 155, "sku7": 345, "sku8": 315, "sku9": 246, "sku10": 75,
}
PRICES_DOLLARS = {sku: cents / 100.0 for sku, cents in PRICES_CENTS.items()}
SKUS = list(PRICES_CENTS)
TAX_PERCENT = 7


def integer_total(cart):
    """Integer cents throughout. Ties round up, exactly and reproducibly."""
    subtotal = sum(PRICES_CENTS[sku] * qty for sku, qty in cart.items())
    tax = (2 * subtotal * TAX_PERCENT + 100) // 200
    return subtotal + tax


def float_total(pairs):
    """Floating point dollars, accumulated in the given order."""
    subtotal = 0.0
    for sku, qty in pairs:
        subtotal += PRICES_DOLLARS[sku] * qty
    tax = subtotal * (TAX_PERCENT / 100.0)
    return int(math.floor(subtotal * 100 + 0.5) + math.floor(tax * 100 + 0.5))


def money(cents):
    return "$%d.%02d" % (cents // 100, cents % 100)


def random_cart(rng):
    size = rng.randint(1, 6)
    return {sku: rng.randint(1, 9) for sku in rng.sample(SKUS, size)}


def part_one_how_often():
    print("1. How often the two disagree")
    print("   " + "-" * 60)
    rng = random.Random(7)
    trials = 400000
    disagreements = []
    half_cent_carts = 0
    for _ in range(trials):
        cart = random_cart(rng)
        subtotal = sum(PRICES_CENTS[s] * q for s, q in cart.items())
        if subtotal % 100 == 50:
            half_cent_carts += 1
        if float_total(list(cart.items())) != integer_total(cart):
            disagreements.append(cart)
    print("   carts tested:                  %d" % trials)
    print("   totals differing by one cent:  %d  (%.4f%%, about 1 in %d)"
          % (len(disagreements), 100.0 * len(disagreements) / trials,
             round(trials / max(len(disagreements), 1))))
    print("   carts whose subtotal ends .50: %d  (%.2f%%)"
          % (half_cent_carts, 100.0 * half_cent_carts / trials))
    print("   share of those that are wrong: %.1f%%"
          % (100.0 * len(disagreements) / max(half_cent_carts, 1)))
    return disagreements


def part_two_why(cart):
    print()
    print("2. Why it happens")
    print("   " + "-" * 60)
    subtotal = sum(PRICES_CENTS[s] * q for s, q in cart.items())
    exact_tax_dollars = subtotal * TAX_PERCENT / 10000.0
    accumulated = 0.0
    for sku, qty in cart.items():
        accumulated += PRICES_DOLLARS[sku] * qty
    print("   cart: %s" % cart)
    print("   exact subtotal        %s, so the tax is exactly $%r"
          % (money(subtotal), exact_tax_dollars))
    print("   that is a half cent, which is a tie, and ties here round up")
    print()
    print("   float subtotal        %.20f" % accumulated)
    print("   float tax             %.20f" % (accumulated * 0.07))
    print("   no longer a tie, so it rounds down instead")
    print()
    print("   integer total         %s" % money(integer_total(cart)))
    print("   float total           %s" % money(float_total(list(cart.items()))))


def part_three_order_dependence():
    print()
    print("3. The same cart, two different prices")
    print("   " + "-" * 60)
    cart = {"sku1": 2, "sku3": 6, "sku9": 6, "sku4": 2}
    print("   cart: %s" % cart)
    by_total = {}
    for ordering in itertools.permutations(cart.items()):
        by_total.setdefault(float_total(ordering), []).append(ordering)
    for total in sorted(by_total):
        orderings = by_total[total]
        names = " then ".join(sku for sku, _ in orderings[0])
        print("   float charges %s for %d of the %d orderings, e.g. %s"
              % (money(total), len(orderings),
                 sum(len(v) for v in by_total.values()), names))
    integer_answers = set(integer_total(dict(o))
                          for o in itertools.permutations(cart.items()))
    print("   integer charges %s for all of them"
          % ", ".join(money(t) for t in sorted(integer_answers)))
    print()
    print("   A customer who adds the fries last is billed a different amount")
    print("   than one who adds them third. Same items, same prices.")


def part_four_smallest():
    print()
    print("4. The smallest cart that reproduces it")
    print("   " + "-" * 60)
    for size in range(2, 13):
        for combo in itertools.combinations_with_replacement(SKUS, size):
            cart = {}
            for sku in combo:
                cart[sku] = cart.get(sku, 0) + 1
            subtotal = sum(PRICES_CENTS[s] * q for s, q in cart.items())
            if subtotal % 100 != 50:
                continue
            if float_total(list(cart.items())) != integer_total(cart):
                print("   %d items across %d lines: %s"
                      % (size, len(cart), cart))
                print("   subtotal %s, integer total %s, float total %s"
                      % (money(subtotal), money(integer_total(cart)),
                         money(float_total(list(cart.items())))))
                return
    print("   none found up to 12 items")


if __name__ == "__main__":
    print()
    print("Integer cents against floating point dollars, same rounding rule")
    print("=" * 66)
    print()
    found = part_one_how_often()
    if found:
        part_two_why(found[0])
    part_three_order_dependence()
    part_four_smallest()
    print()
