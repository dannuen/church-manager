"""The one app color the pastor picks in Settings, and the math that keeps text readable on it.

Standard library only, pure functions. Colors are ``"#rrggbb"`` text; channels are whole numbers 0-255.
``web/style.css`` builds the gradient from ``--accent-base``: the light end is
``color-mix(in srgb, base, #ffffff 15%)`` and the dark end ``color-mix(in srgb, base, #000000 30%)``.
Every channel goes down from the light end to the dark end, so the 2 ends are the worst places for the
text on the gradient: :func:`theme` checks the text on both.
"""

import re

HEX = re.compile(r"#[0-9a-fA-F]{6}")  # the only form of an app color: "#" and 6 hex digits
WHITE, BLACK = "#ffffff", "#000000"
DARK_TEXT = "#151515"  # --text of web/style.css
LIGHT_SHARE, DARK_SHARE = 15, 30  # % of white in the light end, % of black in the dark end
LIGHT_SURFACES = ("#ffffff", "#f7f7f6", "#f2f2f1")  # --surface, --ground, --raised of web/style.css
MIN_CONTRAST = 4.6  # WCAG AA asks 4.5; the margin covers the rounding of the browser
SHARES = range(0, 101, 5)  # a nudge goes in 5% steps: 0, 5, ... 100


def _rgb(color):
    """``"#1f5c99"`` -> ``(31, 92, 153)``. Anything that is not ``#rrggbb`` raises ``ValueError``."""
    if not isinstance(color, str) or HEX.fullmatch(color) is None:
        raise ValueError(f"not a #rrggbb color: {color!r}")
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return "#" + "".join(f"{c:02x}" for c in rgb)


def mix(a, b, share_of_b):
    """CSS ``color-mix(in srgb, a, b share_of_b%)``: a straight blend of the sRGB channels, rounded
    half up to a whole channel. ``share_of_b`` is a whole percent from 0 to 100."""
    if not 0 <= share_of_b <= 100:
        raise ValueError(f"share must be 0 to 100: {share_of_b!r}")
    return _hex((x * (100 - share_of_b) + y * share_of_b + 50) // 100 for x, y in zip(_rgb(a), _rgb(b)))


def luminance(color):
    """WCAG 2 relative luminance of ``color``: 0.0 (black) to 1.0 (white)."""
    def linear(channel):
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG 2 contrast ratio of 2 colors: 1.0 (same) to 21.0 (black on white)."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ends(base):
    """The 2 ends of the gradient made from ``base``: ``(light, dark)``."""
    return mix(base, WHITE, LIGHT_SHARE), mix(base, BLACK, DARK_SHARE)


def _worst_on_ends(text_color, base):
    return min(contrast(text_color, end) for end in ends(base))


def _nudge(color, toward, good):
    """``(share, nudged color)``: the first share in :data:`SHARES` where ``good(nudged)`` is true."""
    for share in SHARES:
        nudged = mix(color, toward, share)
        if good(nudged):
            return share, nudged
    raise ValueError(f"no readable nudge for {color}")  # never: 100% is pure black or white


def theme(color):
    """The 4 CSS values the page head sets for the app color ``color`` (``#rrggbb``):

    - ``--accent``: the color as saved (lower case);
    - ``--accent-base``: the color the gradient is made from, nudged (5% steps) so the text on it reads on
      both ends with a contrast of at least :data:`MIN_CONTRAST`. White text nudges the base toward black,
      dark text (``#151515``) toward white; the smaller nudge wins, white on a tie;
    - ``--on-accent``: that text color;
    - ``--accent-text``: the color nudged toward black until it reads as text on the light surfaces.
    """
    color = _hex(_rgb(color))  # checked, lower case
    white = _nudge(color, BLACK, lambda base: _worst_on_ends(WHITE, base) >= MIN_CONTRAST)
    dark = _nudge(color, WHITE, lambda base: _worst_on_ends(DARK_TEXT, base) >= MIN_CONTRAST)
    (_share, base), text_color = (white, WHITE) if white[0] <= dark[0] else (dark, DARK_TEXT)
    _share, accent_text = _nudge(color, BLACK,
                                 lambda c: all(contrast(c, s) >= MIN_CONTRAST for s in LIGHT_SURFACES))
    return {"--accent": color, "--accent-base": base, "--on-accent": text_color, "--accent-text": accent_text}
