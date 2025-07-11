Berlin Traffic Detection data is provided monthly as hourly values ​​from lane-accurate traffic detectors and aggregated across the directional cross-sections of the streets.

Each CSV archive contains the following data fields:

Detectors:

detid_15 - Detector ID (15-digit number).
tag - Date
stunde - Hour of the day for which the measured values ​​were recorded (8 => 08:00 - 08:59).
qualitaet - Represents the proportion of flawless measurement intervals available for the hour: 1.0 = 100%. Hourly values ​​with less than 75% are not considered.
q_kfz_det_hr - Number of all motor vehicles in the hour.
v_kfz_det_hr - Average speed [km/h] across all motor vehicles in the hour.
q_pkw_det_hr - Number of all passenger cars in the hour.
v_pkw_det_hr - Average speed [km/h] across all cars per hour.
q_lkw_det_hr - Number of all trucks per hour.
v_lkw_det_hr - Average speed [km/h] across all trucks per hour.

Measurement cross-sections:

mq_name - ID of the measurement cross-section.
tag - Date
stunde - Hour of the day for which the measured values ​​were determined (8 => 08:00 - 08:59).
qualitaet - Due to the procedure, this value is always 1.0, i.e., a valid hourly value was available for all detectors belonging to this measurement cross-section.
If individual detectors are missing, no value is calculated for the measurement cross-section.
q_kfz_mq_hr - Number of all motor vehicles per hour.
v_kfz_mq_hr - Average speed [km/h] across all motor vehicles per hour.
q_pkw_mq_hr - Number of all cars per hour.
v_pkw_mq_hr - Average speed [km/h] across all cars per hour.
q_lkw_mq_hr - Number of all trucks per hour.
v_lkw_mq_hr - Average speed [km/h] across all trucks per hour.

Notes:
* There may be slight deviations between the number of all motor vehicles (q_kfz_det_hr) and the total for cars (q_pkw_det_hr) and trucks (q_lkw_det_hr). This results from rounding errors due to the selected method.
* Hourly values ​​are only generated for the detectors if valid data is available for at least 75% of the measurement intervals within an hour. If this is not the case, the corresponding hourly value is missing from the csv archive.
* If a valid hourly value is not available for ALL detectors in a measurement cross-section for an hour, no hourly value is generated for the measurement cross-section.

The location of the detectors and the assignment of the individual detectors to a directional measurement cross-section can be found in the file Master Data_Traffic Detection_Berlin.xlsx.

This contains the following data sheets:
(1) DET
Assignment of the detector ID (DET_ID15) to the ID of the measurement cross-section (MQ_ID15).
The LANE column contains information about the lane position (HF_R - 1st lane from the right on the main carriageway, HR_2vr - 2nd lane from the right on the main carriageway, ...).

(2) MQ
Data of the measurement cross-section with the following columns:

MQ_ID15 - ID of the measurement cross-section.
MQ_SHORT_NAME - Short name of the measurement cross-section.
POSITION - Name of the street.
POSITION_DETAIL - Description of the road section.
DIRECTION - Destination
ORIENTATION - Direction of travel
X_GK4 - X coordinate (Gauss-Krüger 4)
Y_GK4 - Y coordinate (Gauss-Krüger 4)
NUMBER_DET - Number of detectors belonging to the measurement cross-section.