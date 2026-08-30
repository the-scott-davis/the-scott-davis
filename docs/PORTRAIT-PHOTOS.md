# Shooting a photo that works as ASCII

ASCII has one channel: tone. No colour, no line, no edge detection, just how
dark each cell is. So an ASCII portrait is not a drawing of your face. It is a
drawing of **the shadows on your face**. Everything below follows from that.

The practical consequence is unintuitive: the photograph you want here is not a
good headshot. Good headshot lighting is soft and even, which flatters skin and
erases exactly the structure ASCII needs.

---

## The 10-second test

Open the photo on your phone, take any editor, and **drag saturation to zero.**

That grey image is precisely what the converter sees. If you still read as you,
the ASCII will work. If it goes flat and doughy, no amount of tuning will save
it, because the information is already gone.

To put a number on it:

```bash
python -m profilecard.portrait --analyze your-shot.jpg
```

You need **edge strength 130+** out of 255. For calibration, three real results:

| Source | Score | Outcome |
|---|---|---|
| Studio-style headshot, overcast light, green polo | 93 | blob |
| Beach selfie, midday sun, cap and sunglasses | 95 | blob |
| Flat two-tone logo | 151 | crisp |

Both of those photographs look perfectly contrasty in colour. In grey they are
nearly flat. That is the trap this whole document exists to avoid.

---

## The setup

### 1. One light. Hard. From the side.

This is 80% of the result; everything else is refinement.

- **Position:** roughly 45° to one side of the camera, and 30–45° above eye
  level. You are trying to cast the nose's shadow across one cheek.
- **Hard**, meaning physically small relative to your head: a bare bulb, direct
  sun, a phone torch a few feet away. Hard light makes shadows with *sharp
  edges*, and sharp tonal edges are the only thing ASCII can draw with.
- **Not** a softbox, ring light, overcast sky, or open shade. Those are soft
  sources. They wrap light around the face and dissolve the shadow edges.

The classical names for what you want are **Rembrandt** lighting (a small
triangle of light on the shadow-side cheek) or **split** lighting (half the face
lit, half in shadow). Either is ideal.

### 2. Do not fill the shadows

Every instinct from ordinary portraiture says to bounce light back into the dark
side. Resist it. Let the shadow side go genuinely dark, three or four stops
below the lit side. That gap *is* the picture.

### 3. Dark background, and stand away from it

Your face wants to be much brighter than whatever is behind it. A dark wall, an
open doorway into an unlit room, a dark blanket. Put a few feet between you and
it so the light does not spill onto it.

Avoid anything busy. Foliage, bookshelves, and beach scenes all generate strong
tonal detail that competes with your face for the same handful of characters.

### 4. Wear something dark

This is a specific, measured failure mode. In the headshot above, the subject's
skin measured luminance 134 and his green polo measured 136, two levels apart
out of 255. In colour they are obviously different; in grey the shoulders and
the face are the same object. Charcoal or black solves it. So does a plain white
shirt, in the other direction. Mid-tone anything is the risk.

### 5. No sunglasses. No hat brim over the eyes.

Eyes, eyebrows and eye sockets carry more identity than any other feature.
Sunglasses delete them. A cap brim in bright sun throws the entire upper face
into flat shade, which is what happened to the beach photo: plenty of global
contrast, none of it on the face.

Ordinary glasses are usually fine, but watch for reflections blanking the lenses.

### 6. Fill the frame

Head plus a sliver of shoulder. Face square to the camera or turned very
slightly. Symmetry helps a viewer resolve a face from very few cues, and you are
working with very few cues.

### 7. Resolution barely matters

1200–1600px on the long edge is plenty. At 72 columns the converter averages
roughly 10 source pixels into every character; anything beyond about 3 is
discarded. Any phone from the last decade already exceeds this several times
over. **If a portrait looks soft, it is never a resolution problem.**

---

## Four setups that actually work

**Bare desk lamp.** Take the shade off. Put it to one side, slightly above head
height, a few feet away. Turn every other light in the room off. Cheapest
reliable option, and repeatable.

**Window, side-on.** Stand shoulder-to-the-glass, three or four feet away, in an
otherwise dark room, on a bright day. Turn the room lights off. Direct sun
through the window is better than a north-facing window.

**Low sun, outdoors.** Early morning or the hour before sunset, turned so the sun
rakes across your face from the side. Midday sun is the failure case, not this.

**Phone torch.** Have someone hold a second phone at arm's length, off to one
side and above your eye line, in a dark room. It is a small hard source, which
is exactly right.

---

## What to avoid, and why

| Situation | What goes wrong |
|---|---|
| Overcast, open shade, north window | Soft and flattering; no shadow edges at all |
| Midday sun overhead | Flat forehead, dark eye pits, no side modelling |
| Ring light or on-camera flash | Light comes from the lens axis, so nothing casts a visible shadow |
| Any hat in bright sun | Whole face drops into even shade |
| Busy background | Competes for the same tonal range as your face |
| Mid-tone clothing | Merges with skin once colour is discarded |

---

## Workflow

Shoot maybe eight frames, varying the light angle each time. Swing the lamp
further round, raise it, lower it. It costs nothing.

Then batch-check them:

```bash
for f in shots/*.jpg; do
  echo "== $f"
  python -m profilecard.portrait --analyze "$f"
done
```

Take the highest edge strength, put it in `portrait.source`, and tune from
there. See [CUSTOMIZING.md](CUSTOMIZING.md#tuning-the-portrait).

If nothing clears 130 and you would rather not reshoot, `mode: pixel` renders
photographs well precisely because it keeps the colour that ASCII has to discard.
