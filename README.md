# Car Diary for Home Assistant

A custom integration that brings your cars from
[Car Diary](https://www.car-diary.net) into Home Assistant: mileage, fuel,
documents and reminders, one device per car.

> **Unofficial.** Car Diary publishes no API. This integration talks to the one
> behind `web.car-diary.net`, so it can stop working whenever that changes. It
> is not affiliated with or endorsed by Car Diary. It only reads data.

## Sensors

Each car in your account becomes a device with:

| Sensor | Notes |
|---|---|
| Mileage | the car's photo from Car Diary as the entity picture |
| Average consumption | L/100 km, as Car Diary calculates it |
| Last refuel | date; station, fuel, mileage and full-tank flag as attributes |
| Last refuel volume / cost, last fuel price | |
| Fuel cost this month | |
| Expenses this year | refuels, repairs and documents; the split is in the attributes |
| Last repair | date; name, mileage and price as attributes |
| Next reminder | date of the soonest active reminder; the next ten as an attribute |
| Warranty until | only if the car has a warranty date |
| Vignette, liability insurance, casco, technical inspection, vehicle tax | expiry date, with `days_left` and `expired` attributes; created only for documents the car has |

Money is requested in Home Assistant's configured currency. Data is refreshed
every 30 minutes.

## Installation

### HACS

1. HACS → three-dot menu → **Custom repositories**.
2. Add `https://github.com/simonzhekoff/cardiary-ha` as an **Integration**.
3. Install **Car Diary** and restart Home Assistant.

### Manual

Copy `custom_components/car_diary` into the `custom_components` folder of your
Home Assistant configuration and restart.

## Setup

**Settings → Devices & services → Add integration → Car Diary**, then sign in
with the email and password of your Car Diary account.

- Only the session token is stored, not the password. If the token is rejected
  later, Home Assistant asks you to sign in again.
- Accounts that sign in only with Google, Facebook or Apple have no password
  and cannot be added yet.

## Known limits

- Read-only: nothing is written back to Car Diary.
- Records of cars you have deleted in the app are ignored.
- Mileage-based reminders are not shown, only dated ones.
