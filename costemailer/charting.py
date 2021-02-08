import os
import tempfile

import matplotlib.pyplot as plt
import pandas as pd


def plot_data(data):
    dates = []
    costs = []
    units = "USD"

    if data:
        return (None, None)

    for datum in data:
        values = datum["values"][0]
        units = values["cost"]["total"]["units"]
        dates.append(values["date"])
        costs.append(values["cost"]["total"]["value"])

    df = pd.DataFrame({"Dates": dates, units: costs})
    bar = df[units].plot.bar(title="Cost", x="Dates", xlabel="Dates", y=units, ylabel=units)
    fig = bar.get_figure()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    fig.savefig(tmp.name)
    return (tmp, tmp.name)
