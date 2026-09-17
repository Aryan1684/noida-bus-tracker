from services.gps_service import get_noida_electric_buses

buses = get_noida_electric_buses()

print("Total buses:", len(buses))

for bus in buses[:10]:
    print(bus)