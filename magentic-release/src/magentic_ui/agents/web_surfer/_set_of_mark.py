import io
from typing import BinaryIO, Dict, List, Tuple, cast

from PIL import Image, ImageDraw, ImageFont

from ...tools.playwright.types import DOMRectangle, InteractiveRegion

"""
This module provides functionality to annotate screenshots with numbered markers for interactive regions.
It handles marking visible elements as well as tracking elements that are above or below the viewport.
"""

TOP_NO_LABEL_ZONE = 20  # Don't print any labels close the top of the page


def add_set_of_mark(
    screenshot: bytes | Image.Image | io.BufferedIOBase,
    ROIs: Dict[str, InteractiveRegion],
    use_sequential_ids: bool = False,
) -> Tuple[Image.Image, List[str], List[str], List[str], Dict[str, str]]:
    """
    Add numbered markers to a screenshot for each interactive region.

    Args:
        screenshot (bytes | Image.Image | io.BufferedIOBase): The screenshot image as bytes, PIL Image, or file-like object
        ROIs (Dict[str, InteractiveRegion]): Dictionary mapping element IDs to their interactive regions
        use_sequential_ids (bool): If True, assigns sequential numbers to elements instead of using original IDs

    Returns:
        Tuple containing:
        - Image.Image: Annotated image
        - List[str]: List of visible element IDs
        - List[str]: List of element IDs above viewport
        - List[str]: List of element IDs below viewport
        - Dict[str, str]: Mapping of displayed IDs to original element IDs
    """
    if isinstance(screenshot, Image.Image):
        return _add_set_of_mark(screenshot, ROIs, use_sequential_ids)

    if isinstance(screenshot, bytes):
        screenshot = io.BytesIO(screenshot)

    image = Image.open(cast(BinaryIO, screenshot))
    comp, visible_rects, rects_above, rects_below, id_mapping = _add_set_of_mark(
        image, ROIs, use_sequential_ids
    )
    image.close()
    return comp, visible_rects, rects_above, rects_below, id_mapping


def _add_set_of_mark(
    screenshot: Image.Image,
    ROIs: Dict[str, InteractiveRegion],
    use_sequential_ids: bool = True,
) -> Tuple[Image.Image, List[str], List[str], List[str], Dict[str, str]]:
    """
    Internal implementation for adding markers to the screenshot.

    Args:
        screenshot (Image.Image): PIL Image to annotate
        ROIs (Dict[str, InteractiveRegion]): Dictionary of interactive regions
        use_sequential_ids (bool): Whether to use sequential numbers instead of original IDs

    Returns:
        Same as :func:`add_set_of_mark`
    """
    visible_rects: List[str] = []
    rects_above: List[str] = []  # Scroll up to see
    rects_below: List[str] = []  # Scroll down to see
    id_mapping: Dict[str, str] = {}  # Maps new IDs to original IDs

    base = screenshot.convert("RGBA")

    # First pass to identify all rectangles
    for original_id, roi in ROIs.items():
        # Handle options separately and add to visible only
        if roi.get("tag_name") == "option" or roi.get("tag_name") == "input, type=file":
            if original_id not in visible_rects:
                visible_rects.append(original_id)
            continue

        # Check each rectangle for the element
        for rect in roi["rects"]:
            if not rect or rect["width"] * rect["height"] == 0:
                continue

            mid = (
                (rect["right"] + rect["left"]) / 2.0,
                (rect["top"] + rect["bottom"]) / 2.0,
            )

            # Only process if x coordinate is valid
            if 0 <= mid[0] < base.size[0]:
                # Add to exactly one list based on y coordinate
                if mid[1] < 0 and original_id not in rects_above:
                    rects_above.append(original_id)
                elif mid[1] >= base.size[1] and original_id not in rects_below:
                    rects_below.append(original_id)
                elif 0 <= mid[1] < base.size[1] and original_id not in visible_rects:
                    visible_rects.append(original_id)

    # Create new sequential IDs for all rectangles
    next_id = 1
    original_to_new: Dict[str, str] = {}  # Add reverse mapping

    # Helper function to create new mapped IDs
    def map_ids(original_ids: List[str]) -> List[str]:
        nonlocal next_id, original_to_new
        new_ids: List[str] = []
        for original_id in original_ids:
            new_id = str(next_id)
            id_mapping[new_id] = original_id
            original_to_new[original_id] = new_id  # Store reverse mapping
            new_ids.append(new_id)
            next_id += 1
        return new_ids

    if use_sequential_ids:
        # Map IDs in sequence: visible first, then above, then below
        new_visible_rects = map_ids(visible_rects)
        new_rects_above = map_ids(rects_above)
        new_rects_below = map_ids(rects_below)
    else:
        # Use original IDs but still maintain the mapping
        new_visible_rects = visible_rects.copy()
        new_rects_above = rects_above.copy()
        new_rects_below = rects_below.copy()
        # Create identity mapping for all IDs
        for id_list in [visible_rects, rects_above, rects_below]:
            for original_id in id_list:
                id_mapping[original_id] = original_id
                original_to_new[original_id] = original_id

    # Drawing code remains the same
    fnt = ImageFont.load_default(14)
    overlay = Image.new("RGBA", base.size)
    draw = ImageDraw.Draw(overlay)

    # Much simpler and faster lookup using the reverse mapping
    for original_id, roi in ROIs.items():
        if roi.get("tag_name") == "option":
            continue

        new_id = original_to_new.get(original_id)
        if new_id is None:
            continue  # Skip if no mapping found

        for rect in roi["rects"]:
            if not rect or rect["width"] * rect["height"] == 0:
                continue

            mid = (
                (rect["right"] + rect["left"]) / 2.0,
                (rect["top"] + rect["bottom"]) / 2.0,
            )

            if 0 <= mid[0] < base.size[0] and 0 <= mid[1] < base.size[1]:
                _draw_roi(draw, new_id, fnt, rect)

    comp = Image.alpha_composite(base, overlay)
    overlay.close()

    return comp, new_visible_rects, new_rects_above, new_rects_below, id_mapping


def _draw_roi(
    draw: ImageDraw.ImageDraw,
    idx: str | int,  # Fix type hint to allow both string and int indices
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    rect: DOMRectangle,
) -> None:
    """
    Draw a single region of interest on the image.

    Args:
        draw (ImageDraw.ImageDraw): PIL ImageDraw object
        idx (str | int): Index/ID to display on the marker
        font (ImageFont.FreeTypeFont | ImageFont.ImageFont): Font to use for the marker text
        rect (DOMRectangle): Rectangle coordinates for the region
    """
    color = (255, 0, 0, 255)  # Red color for outline
    text_color = (255, 255, 255, 255)  # White text for better contrast

    roi = ((rect["left"], rect["top"]), (rect["right"], rect["bottom"]))

    # Adjust label position if too close to top of screen
    label_location = (rect["right"], rect["top"])
    label_anchor = "rb"

    if label_location[1] <= TOP_NO_LABEL_ZONE:
        label_location = (rect["right"], rect["bottom"])
        label_anchor = "rt"

    draw.rectangle(roi, outline=color, width=2)

    bbox = draw.textbbox(
        label_location, str(idx), font=font, anchor=label_anchor, align="center"
    )
    bbox = (bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3)
    draw.rectangle(bbox, fill=color)

    draw.text(
        label_location,
        str(idx),
        fill=text_color,
        font=font,
        anchor=label_anchor,
        align="center",
    )
