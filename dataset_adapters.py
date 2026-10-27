"""Source-specific decoders. Output units: seconds, degrees, km/h, dB-Hz.

Adapters never manufacture absent RF measurements, attack labels or independent
attitude. DataFrame attrs carry the source contract alongside actual columns.
"""
import io
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

CMU_COLUMNS = {'time', 'position_x', 'position_y', 'velocity_x', 'velocity_y'}


def cmu_flight_dataframe(data):
    """Published CMU flight CSV contract; commanded cruise speed is NOT speed.

Coordinates/velocities are the released GNSS/INS solution, not independent
ground truth. Body acceleration and GPS-aided attitude are not imported as INS.
"""
    if not CMU_COLUMNS.issubset(data.columns):
        raise ValueError('CMU flight columns missing')
    values = data[list(CMU_COLUMNS)].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(values).all().all():
        raise ValueError('Non-finite CMU measurement')
    if len(values) < 2 or np.any(np.diff(values.time) <= 0):
        raise ValueError('CMU flight clock must increase')
    frame = pd.DataFrame(dict(timestamp_s=values.time.to_numpy(),
        lat=values.position_y.to_numpy(), lon=values.position_x.to_numpy(),
        speed_kmh=np.hypot(values.velocity_x, values.velocity_y).to_numpy()*3.6,
        horizontal_accuracy_m=2.))
    frame.attrs['source'] = dict(adapter='cmu-flight-v1', independent_imu=False,
        speed_origin='Measured horizontal velocity norm; commanded cruise speed ignored',
        position_uncertainty_origin='Published GNSS/INS 2m RMS horizontal specification; conservative component sigma 2m',
        notes='DJI Matrice 100 / MicroStrain 3DM-GX5-45 GNSS/INS output. '
              'No C/N0, no independent attitude, no independent position reference; nominal energy-study flight.')
    return frame


def ecef_to_geodetic(x, y, z):
    """WGS84 Bowring conversion for near-Earth navigation solutions."""
    a, b = 6378137., 6356752.314245
    e2, ep2 = 1 - (b/a)**2, (a/b)**2 - 1
    p = np.hypot(x, y)
    theta = np.arctan2(z*a, p*b)
    lat = np.arctan2(z + ep2*b*np.sin(theta)**3,
                     p - e2*a*np.cos(theta)**3)
    lon = np.arctan2(y, x)
    return np.degrees(lat), np.degrees(lon)


def _matrix(contents, name, widths):
    values = np.asarray(contents[name], dtype=float)
    # Published GRID .mat arrays have fields on rows (transpose per readme).
    if values.ndim != 2 or values.shape[0] not in widths:
        raise ValueError(f'{name}: beklenmeyen GRID matrisi; sütun tanımı gerekli')
    return values.T


def texbat_navsol(contents, channel_contents=None):
    nav = _matrix(contents, 'navsol', (12, 13))
    valid = np.isfinite(nav[:, :12]).all(axis=1) & (nav[:, 11] >= 2)
    valid &= (np.linalg.norm(nav[:, 3:6], axis=1) > 6e6)
    nav = nav[valid]
    if not len(nav):
        raise ValueError('TEXBAT içinde geçerli standart konum çözümü yok')
    times = nav[:, 0]*604800 + nav[:, 1] + nav[:, 2]
    lat, lon = ecef_to_geodetic(*nav[:, 3:6].T)
    phi, lam = np.radians(lat), np.radians(lon)
    vx, vy, vz = nav[:, 7:10].T
    east = -np.sin(lam)*vx + np.cos(lam)*vy
    north = -np.sin(phi)*np.cos(lam)*vx - np.sin(phi)*np.sin(lam)*vy + np.cos(phi)*vz
    frame = pd.DataFrame(dict(timestamp_s=times-times[0], lat=lat, lon=lon,
        speed_kmh=np.hypot(east, north)*3.6,
        receiver_clock_bias_m=nav[:, 6], receiver_clock_drift_m_s=nav[:, 10]))
    if np.any(np.diff(times) <= 0):
        raise ValueError('TEXBAT navigasyon zamanı artmıyor')
    if channel_contents is not None:
        channel = _matrix(channel_contents, 'channel', (14,))
        good = (np.isfinite(channel).all(axis=1) & (channel[:, 2] != 9999)
                & (channel[:, 9] == 1) & (channel[:, 8] > 0) & (channel[:, 8] <= 99))
        channel = channel[good]
        epochs = pd.DataFrame(dict(time=channel[:, 2]*604800+channel[:, 3]+channel[:, 4],
                                   cn0=channel[:, 8]))
        epochs = epochs.groupby('time', as_index=False).cn0.mean().sort_values('time')
        merged = pd.merge_asof(pd.DataFrame({'time': times}), epochs,
                               on='time', direction='backward', tolerance=.5)
        frame['cn0'] = merged.cn0.to_numpy()
        from code_carrier import grid_cmc, FAST_WINDOW_S, FAST_MIN_SAMPLES
        cmc = grid_cmc(_matrix(channel_contents, 'channel', (14,)))
        if not cmc.empty:
            cmc = pd.merge_asof(pd.DataFrame({'time': times}), cmc.sort_values('time'),
                                on='time', direction='backward', tolerance=.5)
            for column in ('cmc_epoch_s', 'cmc_rates', 'cmc_channels', 'cmc_rate_m_s'):
                frame[column] = cmc[column].to_numpy()
        fast_cmc = grid_cmc(_matrix(channel_contents, 'channel', (14,)),
                            window_s=FAST_WINDOW_S, min_samples=FAST_MIN_SAMPLES)
        if not fast_cmc.empty:
            fast_cmc = pd.merge_asof(pd.DataFrame({'time': times}), fast_cmc.sort_values('time'),
                                     on='time', direction='backward', tolerance=.5)
            for column in ('cmc_epoch_s', 'cmc_rates', 'cmc_channels', 'cmc_rate_m_s'):
                frame[f'fast_{column}'] = fast_cmc[column].to_numpy()
    frame.attrs['source'] = dict(adapter='texbat-grid-v1',
        receiver_profile='grid-unvalidated',
        speed_origin='ECEF velocity projected to local horizontal plane',
        cn0_origin='Mean of valid channels, backward match <=0.5s',
        labels='unknown; no inferred attack onset', independent_imu=False,
        raw_signal=False, notes='Recorded RF processed by UT GRID receiver; not UAV flight.')
    if channel_contents is not None:
        from code_carrier import CONTRACT
        frame.attrs['source']['cmc_contract'] = CONTRACT
    return frame


def mat_dataframe(contents, channel_contents=None):
    if 'navsol' in contents:
        return texbat_navsol(contents, channel_contents)
    raise ValueError('MAT şeması tanınmıyor. Desteklenen: GRID navsol; adsız matrise alan tahmin edilmez.')


def zurich_zip(archive):
    """Read only documented flight logs; do not extract image/archive paths."""
    members = {Path(name.replace('\\', '/')).name.lower(): name
               for name in archive.namelist() if not name.endswith('/')}
    gps_name = members.get('onbordgps.csv') or members.get('onboardgps.csv')
    if not gps_name:
        return None
    def read(name):
        with archive.open(name) as handle:
            table = pd.read_csv(handle)
        table.columns = table.columns.str.strip()
        return table

    gps = read(gps_name)
    required = ['Timpstemp', 'lat', 'lon', 'fix_type', 'vel_n_m_s', 'vel_e_m_s']
    if not set(required).issubset(gps.columns):
        raise ValueError('Zurich GPS sütun şeması tanınmıyor')
    optional = [column for column in ('alt', 'vel_d_m_s', 's_variance_m_s', 'eph_m', 'num_sat')
                if column in gps.columns]
    numeric = gps[required+optional].apply(pd.to_numeric, errors='raise')
    good = np.isfinite(numeric[required]).all(axis=1) & (numeric.fix_type >= 3)
    gps, numeric = gps.loc[good], numeric.loc[good]
    reordered = int((numeric.Timpstemp.diff() < 0).sum())
    input_rows = len(numeric)
    # Image-aligned logs hold each GPS payload across multiple video frames.
    # Coalesce in original acquisition order BEFORE sorting: sorting first can
    # interleave old/new fixes at the documented sub-frame clock reversals.
    payload = numeric.drop(columns='Timpstemp')
    changed = payload.ne(payload.shift()).any(axis=1)
    numeric = numeric.loc[changed]
    # The release contains small out-of-order timestamps at some image/GPS
    # boundaries. Sort existing observations; never rewrite their clocks.
    numeric = numeric.sort_values('Timpstemp', kind='stable')
    if not len(gps):
        raise ValueError('Zurich içinde geçerli 3D konum yok')
    lat, lon = numeric.lat.to_numpy(), numeric.lon.to_numpy()
    # The released sample already uses decimal degrees, unlike its older readme.
    # Resolve only the two documented representations, consistently for the file.
    unit = 'degrees as stored in published sample'
    if not (np.all(np.abs(lat) <= 90) and np.all(np.abs(lon) <= 180)):
        lat, lon = lat/1e7, lon/1e7
        unit = '1e-7 degrees per bundled readme'
    if not (np.all(np.abs(lat) < 89.999) and np.all(np.abs(lon) <= 180)):
        raise ValueError('Zurich koordinat birimi/aralığı geçersiz')
    clock = numeric.Timpstemp.to_numpy(dtype=float)/1e6
    if np.any(np.diff(clock) <= 0):
        raise ValueError('Zurich GPS zamanı artmıyor')
    frame = pd.DataFrame(dict(timestamp_s=clock-clock[0], lat=lat, lon=lon,
        speed_kmh=np.hypot(numeric.vel_n_m_s, numeric.vel_e_m_s).to_numpy()*3.6))
    if 's_variance_m_s' in numeric:
        frame['speed_accuracy_m_s'] = numeric.s_variance_m_s.to_numpy()
    if 'eph_m' in numeric:
        frame['horizontal_accuracy_m'] = numeric.eph_m.to_numpy()
    frame['heading_deg'] = np.degrees(np.arctan2(numeric.vel_e_m_s, numeric.vel_n_m_s)).to_numpy() % 360
    accel_name = members.get('rawaccel.csv')
    if accel_name:
        imu = read(accel_name)
        required_imu = ['Timpstemp', 'x', 'y', 'z', 'Error_count']
        if not set(required_imu).issubset(imu.columns):
            raise ValueError('Zurich IMU sütun şeması tanınmıyor')
        imu = imu[required_imu].apply(pd.to_numeric, errors='raise')
        imu = imu.loc[np.isfinite(imu).all(axis=1) & (imu.Error_count == 0)].copy()
        imu['time'] = imu.Timpstemp/1e6
        merged = pd.merge_asof(pd.DataFrame({'time': clock}), imu.sort_values('time'),
                               on='time', direction='backward', tolerance=.2)
        for axis in 'xyz':
            frame[f'imu_a{axis}_m_s2'] = merged[axis].to_numpy()
        frame['imu_available'] = merged[['x', 'y', 'z']].notna().all(axis=1).to_numpy()
        frame['imu_frame'] = 'body'
    frame.attrs['source'] = dict(adapter='zurich-mav-v1', coordinate_input=unit,
        input_gps_rows=input_rows, held_gps_rows_removed=input_rows-len(frame),
        out_of_order_boundaries=reordered, time_policy='stable timestamp sort; no clock rewriting',
        speed_origin='Hypotenuse of GNSS north/east velocity, m/s to km/h',
        labels='unknown; no attack annotation supplied', independent_imu=False,
        imu_origin='Raw body accelerometer; backward match <=0.2s; no assumed attitude',
        notes='Real Fotokite flight. Camera UTM reference is not GNSS antenna ground truth. '
              'GPS-assisted onboard pose is not independent heading. No C/N0 supplied.')
    return frame


def zip_dataframe(archive):
    flight = zurich_zip(archive)
    if flight is not None:
        return flight
    navs = [name for name in archive.namelist() if Path(name).name.lower() == 'navsol.mat']
    if len(navs) == 1:
        from scipy.io import loadmat
        nav_name = navs[0]
        channel_name = str(Path(nav_name).with_name('channel.mat')).replace('\\', '/')
        raw = archive.read(nav_name)
        contents = loadmat(io.BytesIO(raw))
        channel = loadmat(io.BytesIO(archive.read(channel_name))) if channel_name in archive.namelist() else None
        frame = mat_dataframe(contents, channel)
        from real_data_catalog import declared_grid_profile
        frame.attrs['source']['receiver_profile'] = declared_grid_profile(hashlib.sha256(raw).hexdigest())
        return frame
    csvs = [name for name in archive.namelist() if name.lower().endswith('.csv')
            and not name.startswith('__MACOSX/')]
    if len(csvs) != 1:
        raise ValueError('ZIP içinde tek bir CSV veya tanınan kaynak paketi olmalı; ilk dosya otomatik seçilmez')
    with archive.open(csvs[0]) as handle:
        return pd.read_csv(handle)
