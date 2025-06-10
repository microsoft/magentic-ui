import matplotlib.pyplot as plt
import matplotlib.style as style
from matplotlib.ticker import PercentFormatter
import os
import argparse
import numpy as np


def create_accuracy_plot(save_path=None, save_dir=None):
    """
    Parameters:
    -----------
    save_path : str, optional
        Filename to save the figure. If None, the figure is not saved.
    save_dir : str, optional
        Directory to save the figure. If provided, the directory will be created
        if it doesn't exist. Default is current directory if save_path is provided.

    Returns:
    --------
    fig, ax : tuple
        Figure and axes objects for further customization if needed.
    """
    style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    plt.rcParams["font.size"] = 16
    plt.rcParams["axes.labelsize"] = 16
    plt.rcParams["axes.titlesize"] = 17
    plt.rcParams["xtick.labelsize"] = 12
    plt.rcParams["ytick.labelsize"] = 12
    plt.rcParams["legend.fontsize"] = 12

    # Data
    models = [
        "Magentic-One",
        "Magentic-UI\n(autonomous)",
        "Magentic-UI +\nSimulated User\n(smarter model)",
        "Magentic-UI +\nSimulated User\n(side-information)",
        "Human",
    ]
    accuracy = [33.72, 30.2, 42.6, 51.9, 92]
    sample_size = 162

    # Calculate 95% confidence intervals for each accuracy
    z = 1.96  # for 95% confidence
    accuracy_frac = np.array(accuracy) / 100.0
    ci_half_width = (
        z * np.sqrt(accuracy_frac * (1 - accuracy_frac) / sample_size) * 100
    )  # convert back to percent

    # Create figure and axis with adjusted figsize for more horizontal space
    fig, ax = plt.subplots(figsize=(9, 6))

    # Custom colors as specified
    dark_magenta = "#8B008B"  # Darker magenta for Magentic-One
    grey = "#808080"  # Grey for Magentic-UI + Simulated Human
    beige = "#F5F5DC"  # Beige for Human

    colors = [grey, dark_magenta, dark_magenta, dark_magenta, beige]
    hatches = [
        "",
        "",
        "///",
        "xx",
        "",
    ]

    # Create custom x positions for more space between bars
    x = np.arange(len(models)) * 2

    # Create separate bars for each model
    bars = []
    for i, (model, acc) in enumerate(zip(models, accuracy)):
        bar = ax.bar(
            x[i],
            acc,
            color=colors[i],
            width=1,
            edgecolor="black",
            linewidth=0.8,
            label=model,
            hatch=hatches[i],
            yerr=ci_half_width[i],
            capsize=8,
        )
        bars.extend(bar)

    # Set x-tick positions and labels
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=0, ha="center")
    # Configure the axes
    ax.set_ylabel("Accuracy (%)", fontweight="bold")
    ax.set_ylim(0, 100)  # Set y-axis from 0 to 100%
    ax.yaxis.set_major_formatter(PercentFormatter())

    # Add grid for y-axis only and put it behind the bars
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)

    # Remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Make left and bottom spines thicker
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)

    # Add legend inside the plot
    legend = ax.legend(
        loc="upper left", frameon=True, framealpha=0.9, edgecolor="lightgray"
    )
    legend.get_title().set_fontweight("bold")

    # Add some padding to the x-axis labels
    plt.xticks(rotation=0, ha="center")

    # Adjust bottom margin to ensure labels fit
    plt.subplots_adjust(bottom=0.15)

    plt.tight_layout()

    # Save the figure in high resolution if path provided
    if save_path:
        if save_dir:
            # Create directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
            full_path = os.path.join(save_dir, save_path)
        else:
            full_path = save_path
        # save as pdf
        plt.savefig(full_path.replace(".png", ".pdf"), dpi=600, bbox_inches="tight")
        # save as png
        plt.savefig(full_path.replace(".pdf", ".png"), dpi=600, bbox_inches="tight")
        print(
            f"Plot saved to: {os.path.abspath(full_path.replace('.png', '.pdf'))} and {os.path.abspath(full_path.replace('.pdf', '.png'))}"
        )

    return fig, ax


if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="plot experimental results")
    parser.add_argument(
        "--save-dir",
        "-d",
        type=str,
        default="plots",
        help="Directory to save the plot (default: plots)",
    )

    args = parser.parse_args()

    # Create and display the plot
    fig, ax = create_accuracy_plot(
        save_path="model_accuracy_comparison.png", save_dir=args.save_dir
    )
