def calculate_event_yield(initial_quantity, final_quantity, sold_quantity):
    """Return stock used, observed yield and a display status for one event.

    No historical value is read or written. The result depends only on the
    event's initial stock, final physical count and registered sale units.
    """
    initial = float(initial_quantity or 0)
    sold = int(sold_quantity or 0)
    if final_quantity is None:
        return None, None, "Pendiente de stock final"

    used = round(initial - float(final_quantity), 3)
    if used > 0:
        return used, round(sold / used, 3), "Calculado"
    if used == 0 and sold == 0:
        return used, None, "Sin consumo"
    return used, None, "Revisar conteo"
