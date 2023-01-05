import matplotlib
import numpy as np
import io

matplotlib.use("agg")
import matplotlib.pyplot as plt  # noqa (can't just do import because of Qt5 installation problems)

SECONDS_IN_DAY = 86400


def get_day_usage_bar(ranges, pixelwidth, pixelheight):

    bar = np.zeros(pixelwidth)

    for rng in ranges:
        start = rng[0]
        if start < 0:
            start = 0
        end = rng[1]
        if end > SECONDS_IN_DAY:
            end = SECONDS_IN_DAY
        for pxl in range(start * pixelwidth // SECONDS_IN_DAY, end * pixelwidth // SECONDS_IN_DAY):
            bar[pxl] = 1

    dpi = 10
    fig = plt.figure(figsize=(len(bar) / dpi, pixelheight / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])  # span the whole figure
    # ax.set_axis_off()
    ax.imshow(bar.reshape(1, -1), cmap="cool", aspect="auto")
    # plt.show()
    f = io.BytesIO()
    plt.savefig(f, format="png")
    plt.close()
    return f.getvalue()
