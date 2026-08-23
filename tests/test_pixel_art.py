"""Tests for the pixel path: run-length encoding must be lossless."""

from PIL import Image

from profilecard.pixel_art import PixelOptions, boxes_to_paths, image_to_pixels, load_boxes

RED, BLUE = (255, 0, 0), (0, 0, 255)


def save(tmp_path, pixels, size):
    img = Image.new("RGB", size)
    img.putdata(pixels)
    path = tmp_path / "art.png"
    img.save(path)
    return path


def replay(w, h, boxes):
    """Paint the boxes back onto a grid so we can compare against the source."""
    grid = [[None] * w for _ in range(h)]
    for b in boxes:
        for y in range(b.y, b.y + b.h):
            for x in range(b.x, b.x + b.w):
                grid[y][x] = b.color
    return grid


class TestLoadBoxes:
    def test_solid_image_is_one_box(self, tmp_path):
        path = save(tmp_path, [RED] * 12, (4, 3))
        w, h, boxes = load_boxes(path)
        assert (w, h) == (4, 3)
        assert len(boxes) == 1
        assert (boxes[0].w, boxes[0].h, boxes[0].color) == (4, 3, "#ff0000")

    def test_horizontal_runs_merge(self, tmp_path):
        path = save(tmp_path, [RED, RED, BLUE, BLUE], (4, 1))
        _, _, boxes = load_boxes(path)
        assert [(b.x, b.w) for b in boxes] == [(0, 2), (2, 2)]

    def test_vertical_stacking_merges(self, tmp_path):
        # Two identical rows should become one box, not two.
        path = save(tmp_path, [RED, BLUE] * 2, (2, 2))
        _, _, boxes = load_boxes(path)
        assert len(boxes) == 2
        assert all(b.h == 2 for b in boxes)

    def test_non_contiguous_rows_do_not_merge(self, tmp_path):
        rows = [RED, RED] + [BLUE, BLUE] + [RED, RED]
        _, _, boxes = load_boxes(save(tmp_path, rows, (2, 3)))
        assert sorted(b.h for b in boxes) == [1, 1, 1]

    def test_encoding_is_lossless(self, tmp_path):
        # The whole optimisation is only safe if it reproduces the image exactly.
        pixels = [RED if (x + y) % 3 else BLUE for y in range(7) for x in range(5)]
        path = save(tmp_path, pixels, (5, 7))
        w, h, boxes = load_boxes(path)
        expected = [["#ff0000" if (x + y) % 3 else "#0000ff" for x in range(5)] for y in range(7)]
        assert replay(w, h, boxes) == expected

    def test_boxes_never_overlap(self, tmp_path):
        pixels = [RED if (x * y) % 4 else BLUE for y in range(9) for x in range(6)]
        w, h, boxes = load_boxes(save(tmp_path, pixels, (6, 9)))
        seen = set()
        for b in boxes:
            for y in range(b.y, b.y + b.h):
                for x in range(b.x, b.x + b.w):
                    assert (x, y) not in seen
                    seen.add((x, y))
        assert len(seen) == w * h  # and they cover everything


class TestPaths:
    def test_one_path_per_colour(self, tmp_path):
        _, _, boxes = load_boxes(save(tmp_path, [RED, BLUE] * 4, (2, 4)))
        paths = boxes_to_paths(boxes)
        assert len(paths) == 2
        assert {c for c, _ in paths} == {"#ff0000", "#0000ff"}

    def test_path_data_is_closed_subpaths(self, tmp_path):
        _, _, boxes = load_boxes(save(tmp_path, [RED] * 4, (2, 2)))
        (_, data), = boxes_to_paths(boxes)
        assert data == "M0 0h2v2h-2z"


class TestConversion:
    def test_respects_width_and_palette(self):
        source = Image.new("RGB", (200, 400))
        source.putdata([(x % 256, y % 256, 128) for y in range(400) for x in range(200)])
        art = image_to_pixels(source, PixelOptions(width=20, palette=8))
        assert art.width == 20
        assert art.height == 40  # aspect preserved
        assert len(art.getcolors(1 << 16)) <= 8

    def test_explicit_height_overrides_aspect(self):
        art = image_to_pixels(Image.new("RGB", (100, 100)), PixelOptions(width=10, height=3))
        assert (art.width, art.height) == (10, 3)

    def test_crop_changes_the_aspect(self):
        source = Image.new("RGB", (100, 100))
        art = image_to_pixels(source, PixelOptions(width=10, crop=(0.0, 0.0, 1.0, 0.5)))
        assert art.height == 5


class TestAnalyze:
    """The verdict must reproduce what was actually observed on real sources."""

    def test_flat_image_is_rejected_for_ascii(self):
        from PIL import Image
        from profilecard.analyze import analyze
        # Strong colour variation, almost no brightness variation -- the exact
        # trap that makes a photo look contrasty and render as a smudge.
        img = Image.new("RGB", (200, 200))
        img.putdata([(200, 100, 90) if (x // 10) % 2 else (95, 155, 110)
                     for y in range(200) for x in range(200)])
        assert analyze(img).verdict == "pixel"

    def test_high_contrast_image_is_accepted(self):
        from PIL import Image
        from profilecard.analyze import analyze
        img = Image.new("RGB", (200, 200))
        img.putdata([(255, 255, 255) if (x // 20) % 2 else (10, 10, 10)
                     for y in range(200) for x in range(200)])
        assert analyze(img).verdict == "ascii"

    def test_mostly_flat_art_with_hard_edges_is_accepted(self):
        from PIL import Image
        from profilecard.analyze import analyze
        # A logo is mostly flat with a few strong edges. Judging by the median
        # would score that near zero and wrongly reject it.
        img = Image.new("RGB", (200, 200), (255, 255, 255))
        for y in range(70, 130):
            for x in range(70, 130):
                img.putpixel((x, y), (10, 10, 10))
        r = analyze(img)
        assert r.local_median < 5      # almost everything is flat
        assert r.verdict == "ascii"    # ...but the edges that exist are strong

    def test_resolution_is_reported_per_cell_not_absolute(self):
        from PIL import Image
        from profilecard.analyze import analyze
        r = analyze(Image.new("RGB", (1000, 1000)), crop=(0.0, 0.0, 1.0, 1.0), columns=100)
        assert r.px_per_cell == 10
