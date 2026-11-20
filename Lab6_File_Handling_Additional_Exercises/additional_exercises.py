"""Activity 6 appendix: three optional dataset exercises (stdlib only).

Requires downloaded Kaggle CSVs. Tiny synthetic fixtures in sample_data/
can be used only by explicitly specifying --demo. No pandas or numpy.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import LAST_NAME, STUDENT_ID
from lab6_core import make_student

BASE = Path(__file__).resolve().parents[1]


def _get(row, name):
    """Look up an exact dataset heading allowing extra outer whitespace/BOM."""
    for key, value in row.items():
        if key and key.strip().lstrip('\ufeff') == name:
            return (value or '').strip()
    raise KeyError(f'Missing expected CSV column: {name!r}. Available: {list(row)}')


def _csv_writer(path, headings):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open('w', encoding='utf-8', newline='')
    writer = csv.DictWriter(f, fieldnames=headings, extrasaction='ignore')
    writer.writeheader()
    return f, writer


def _json_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding='utf-8')
    return path


def _backup(source, backup):
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup)
    return dict(path=str(backup), exists=backup.is_file(),
                identical=backup.read_bytes() == source.read_bytes(),
                size_bytes=backup.stat().st_size)


def web_server_logs(input_path: Path, out_dir: Path, backup_dir: Path, s):
    """Appendix 1: first 1000+ID_SUM records; target HTTP status class."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = (s.seed_digit % 4) + 2
    limit = 1000 + s.id_sum
    selected_csv = out_dir / f'{s.last_name}_{s.student_id}_web_filtered.csv'
    summary_json = out_dir / f'{s.last_name}_{s.student_id}_web_summary.json'
    processed, selected, invalid = 0, 0, 0
    by_status, by_url = Counter(), Counter()
    with input_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        of, writer = _csv_writer(selected_csv, ['IP', 'Time', 'URL', 'Status'])
        with of:
            for row in reader:
                if processed >= limit:
                    break
                processed += 1
                try:
                    ip, time, url, status = (_get(row, k) for k in ('IP','Time','URL','Status'))
                    code = int(status)
                    if not ip or not time or not url or not (100 <= code < 600):
                        raise ValueError('Missing data/invalid status')
                except (KeyError, ValueError, TypeError):
                    invalid += 1
                    continue
                if code // 100 == target:
                    selected += 1
                    by_status[code] += 1
                    by_url[url] += 1
                    writer.writerow(dict(IP=ip, Time=time, URL=url, Status=code))
    top_urls = sorted(by_url.items(), key=lambda it: (-it[1], it[0]))[:5]
    summary = dict(student_id=s.student_id, records_processed=processed,
                   target_status_class=f'{target}xx', invalid_records=invalid,
                   records_in_target_class=selected,
                   count_per_status_code=dict(sorted(by_status.items())),
                   five_most_requested_urls=[{'url': u, 'requests': n} for u,n in top_urls],
                   filtered_csv=str(selected_csv))
    _json_file(summary_json, summary)
    backup = _backup(summary_json, backup_dir / summary_json.name)
    summary.update(json_summary_file=str(summary_json), backup_verification=backup)
    return summary


def mobile_device_usage(input_path: Path, out_dir: Path, backup_dir: Path, s):
    """Appendix 2: OS + user behavior; battery and data usage averages."""
    os_filter = 'Android' if s.seed_digit % 2 == 0 else 'iOS'
    behavior = (s.seed_digit % 5) + 1
    output_fields = ['User ID', 'Device Model', 'Operating System',
                     'Battery Drain (mAh/day)', 'Data Usage (MB/day)']
    selected_csv = out_dir / f'{s.last_name}_{s.student_id}_mobile_filtered.csv'
    summary_json = out_dir / f'{s.last_name}_{s.student_id}_mobile_summary.json'
    total, os_matches, selected, invalid = 0, 0, 0, 0
    battery_sum, usage_sum = 0.0, 0.0
    with input_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        of, writer = _csv_writer(selected_csv, output_fields)
        with of:
            for row in reader:
                total += 1
                try:
                    os_val = _get(row, 'Operating System')
                    if os_val.casefold() != os_filter.casefold():
                        continue
                    os_matches += 1
                    if int(_get(row, 'User Behavior Class')) != behavior:
                        continue
                    record = {key: _get(row,key) for key in output_fields}
                    battery = float(record['Battery Drain (mAh/day)'])
                    usage = float(record['Data Usage (MB/day)'])
                    if battery < 0 or usage < 0:
                        raise ValueError('Negative usage')
                except (KeyError, TypeError, ValueError):
                    invalid += 1
                    continue
                writer.writerow(record)
                battery_sum += battery
                usage_sum += usage
                selected += 1
    with selected_csv.open('r', encoding='utf-8-sig', newline='') as f:
        exported_count = sum(1 for _ in csv.DictReader(f))
    summary = dict(student_id=s.student_id, operating_system=os_filter,
        user_behavior_class=behavior, total_records_in_dataset=total,
        records_matching_operating_system=os_matches,
        records_in_target_behavior_class=selected,
        invalid_matching_records=invalid,
        average_battery_drain_mAh_per_day=(battery_sum / selected if selected else None),
        average_data_usage_MB_per_day=(usage_sum / selected if selected else None),
        count_verification=(exported_count == selected),
        exported_row_count=exported_count, exported_csv_file=str(selected_csv))
    _json_file(summary_json, summary)
    backup = _backup(selected_csv, backup_dir / selected_csv.name)
    summary.update(json_summary_file=str(summary_json), backup_file_and_size=backup)
    return summary


def cybersecurity_incidents(input_path: Path, out_dir: Path, backup_dir: Path, s):
    """Appendix 3: target-year incident counts, cost ranking, CSV/JSON/report."""
    target_year = 2015 + s.seed_digit
    selected_csv = out_dir / f'{s.last_name}_{s.student_id}_cyber_filtered.csv'
    summary_json = out_dir / f'{s.last_name}_{s.student_id}_cyber_summary.json'
    report_path = out_dir / f'{s.last_name}_{s.student_id}_cyber_report.txt'
    total, selected, invalid_losses, money_count = 0, 0, 0, 0
    money_total = 0.0
    attack_count = Counter()
    candidates = []
    with input_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('Missing CSV header')
        of, writer = _csv_writer(selected_csv, reader.fieldnames)
        with of:
            for row in reader:
                total += 1
                try:
                    year = int(_get(row, 'Year'))
                except (KeyError, TypeError, ValueError):
                    continue
                if year != target_year:
                    continue
                selected += 1
                writer.writerow(row)
                attack_count[_get(row, 'Attack Type') or '(missing)'] += 1
                try:
                    loss = float(_get(row, 'Financial Loss (in Million $)'))
                    if loss < 0 or loss != loss:
                        raise ValueError('Negative or NaN')
                except (KeyError, TypeError, ValueError):
                    invalid_losses += 1
                    continue
                money_count += 1
                money_total += loss
                candidates.append((loss, selected, row))
    # Python stable sort retains dataset order for equal losses.
    costliest = sorted(candidates, key=lambda item: -item[0])[:5]
    top5 = [{'rank': i, 'financial_loss_usd_millions': loss,
             'source_record_number_in_target_year': order, 'record': row}
            for i, (loss, order, row) in enumerate(costliest, 1)]
    summary = dict(student_id=s.student_id, target_year=target_year,
                   total_records_in_dataset=total,
                   incidents_in_target_year=selected,
                   count_per_attack_type=dict(sorted(attack_count.items())),
                   total_financial_loss_usd_millions=round(money_total, 4),
                   average_financial_loss_usd_millions=(round(money_total / money_count, 4)
                                                         if money_count else None),
                   incidents_with_valid_loss=money_count,
                   incidents_with_invalid_loss=invalid_losses,
                   five_costliest_incidents=top5,
                   filtered_csv_file=str(selected_csv))
    _json_file(summary_json, summary)
    backup = _backup(summary_json, backup_dir / summary_json.name)
    lines = [
        'CYBERSECURITY INCIDENT REPORT',
        f'Student: {s.last_name} ({s.student_id})',
        f'Target year: {target_year}',
        f'Total records scanned: {total}',
        f'Incidents in target year: {selected}',
        'Attack types and counts:',
        *[f'  {k}: {n}' for k,n in sorted(attack_count.items())],
        f'Total financial loss (USD millions): {money_total:.4f}',
        'Average loss per incident with valid loss (USD millions): '
        + (f'{money_total / money_count:.4f}' if money_count else 'N/A'),
        f'Invalid / unavailable financial losses: {invalid_losses}',
        'Five costliest incidents (dataset order breaks ties):',
        *[f'  #{i}: {loss:.4f} USD million; {row}'
          for i,(loss,_,row) in enumerate(costliest,1)],
        f'CSV: {selected_csv}', f'JSON: {summary_json}',
        f'Backup: {backup["path"]}',
        f'Backup verified identical: {backup["identical"]}',
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    summary.update(json_summary_file=str(summary_json),
                   backup_verification=backup, report_file=str(report_path))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exercise', choices=['web', 'mobile', 'cyber', 'all'])
    parser.add_argument('--demo', action='store_true', help='Use synthetic sample CSVs, not the required Kaggle originals')
    parser.add_argument('--web-file', type=Path)
    parser.add_argument('--mobile-file', type=Path)
    parser.add_argument('--cyber-file', type=Path)
    args = parser.parse_args()
    s = make_student(os.environ.get('LAB6_LAST_NAME',LAST_NAME),
                     os.environ.get('LAB6_STUDENT_ID',STUDENT_ID))
    sample = BASE / 'sample_data'
    dataset = BASE / 'data'
    specs = {
        'web': (web_server_logs, args.web_file or ((sample / 'weblog_DEMO.csv') if args.demo else (dataset / 'weblog.csv'))),
        'mobile': (mobile_device_usage, args.mobile_file or ((sample / 'user_behavior_dataset_DEMO.csv') if args.demo else (dataset / 'user_behavior_dataset.csv'))),
        'cyber': (cybersecurity_incidents, args.cyber_file or ((sample / 'Global_Cybersecurity_Threats_DEMO.csv') if args.demo else (dataset / 'Global_Cybersecurity_Threats_2015-2024.csv'))),
    }
    if args.demo:
        print('*** DEMONSTRATION DATA ONLY — NOT KAGGLE RESULTS ***')
    for key in (specs if args.exercise == 'all' else (args.exercise,)):
        fn, source = specs[key]
        if not source.is_file():
            raise FileNotFoundError(f'Cannot find {source}. Download original Kaggle CSV into data/ or use --demo.')
        result = fn(source, BASE / 'output' / 'additional_exercises',
                    BASE / 'backup' / 'additional_exercises', s)
        print(f'\n=== {key.upper()} ===')
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
