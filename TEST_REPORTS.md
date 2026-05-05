# Alfred Test Reports

Last updated: 2026-05-06 Asia/Taipei

This document records the verification rounds used to decide whether the current Alfred iOS + backend build is portable, testable, and ready for partner/demo review.

## Summary

| Area | Result | Notes |
|---|---:|---|
| Backend service | PASS | `alfred.service` active on `YOUR_SERVER` |
| Public API routing | PASS | `/alfred/api/greet` returned HTTP 200 |
| Document upload | PASS | 30/30 in regression test |
| Document analysis / summary | PASS | 30/30 in regression test |
| iOS generic build | PASS | `xcodebuild` completed with `BUILD SUCCEEDED` |
| iPhone install | PASS | Installed bundle `Norika.Alfred` to connected iPhone |
| iPhone launch | PASS | `devicectl` launched Alfred after device was unlocked |
| Total automated backend checks | PASS | 1380/1380 successful |

## Round 1 - Document Analysis Smoke Test

Purpose: prove the new "upload a file, then summarize/analyze it" path works outside the UI before relying on the phone build.

Test path:

1. Request device JWT with `POST /alfred/api/auth/device`.
2. Upload a TXT file with `POST /alfred/api/files/upload`.
3. Analyze the uploaded file with `POST /alfred/api/contract/analyze/{file_id}?output=summary`.
4. Inspect returned Markdown.

Result:

| Check | Result |
|---|---:|
| Device auth returned token | PASS |
| File upload returned `id` | PASS |
| Analysis returned `ok: true` | PASS |
| Output was Traditional Chinese Markdown | PASS |
| Output did not force non-contract text into contract-only fields | PASS |

Observed improvement:

- Before this round, the backend prompt was contract-heavy and could make ordinary documents look like legal reviews.
- After the update, the backend first identifies document type, then gives a general summary, risk/attention list, and next steps. Contract/business-specific fields are only filled when applicable.

Evidence excerpt from smoke test:

```text
ok=True
name=alfred_doc_test.txt
## 一、文件一句話總結
這是阿福系統的產品功能地圖...
## 五、如果這是合約或商務文件
不適用。
```

## Round 2 - iOS Build, Install, Launch

Purpose: verify that another build machine with Xcode and signing can compile the current project and install to a physical iPhone.

Commands used:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild \
  -project /Users/YOUR_USER/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -destination 'generic/platform=iOS' \
  -configuration Debug build
```

Device install:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun devicectl device install app \
  --device E7D552A7-7C53-5E4A-9FFF-7B75CCD98995 \
  /Users/YOUR_USER/Library/Developer/Xcode/DerivedData/Alfred-comiywlbirvcrnfmmzrnhngzvdpy/Build/Products/Debug-iphoneos/Alfred.app
```

Result:

| Check | Result |
|---|---:|
| Xcode project recognized | PASS |
| Swift compile | PASS |
| Link | PASS |
| Code signing | PASS |
| iPhone install | PASS |
| iPhone launch after unlock | PASS |

Build output:

```text
** BUILD SUCCEEDED **
App installed:
• bundleID: Norika.Alfred
```

Warnings observed:

| Warning | Impact |
|---|---|
| `.allowBluetooth` deprecated; should use `.allowBluetoothHFP` | Non-blocking, future cleanup |
| Captured `self` warning in `AmbientRecorder` under future Swift 6 mode | Non-blocking today, should be cleaned before Swift 6 strict migration |

Observed improvement:

- The phone build now includes a manual `文件分析` entry point, so testers do not need to rely only on a voice-triggered upload action.
- The backend and phone build use the same upload + analysis path verified in Round 1.

## Round 3 - 30x Regression Matrix

Purpose: run a broad repeatability check against safe endpoints 30 times each.

Report artifact:

```text
/Users/YOUR_USER/Documents/New project 3/alfred_30x_test_report.json
```

Scope:

- 46 safe automated checks
- 30 repetitions each
- 1380 total checks
- External side-effect actions were not triggered: real phone calls, real email sends, LINE/Telegram push, emergency escalation

Overall result:

| Metric | Value |
|---|---:|
| Test groups | 46 |
| Repetitions per group | 30 |
| Total checks | 1380 |
| Passed | 1380 |
| Failed | 0 |
| Pass rate | 100% |

Detailed result:

| Test group | Passed | Failed |
|---|---:|---:|
| `greet` | 30 | 0 |
| `discover` | 30 | 0 |
| `setup_status` | 30 | 0 |
| `onboard_status` | 30 | 0 |
| `auth_me` | 30 | 0 |
| `todos` | 30 | 0 |
| `calendar` | 30 | 0 |
| `reminders_pending` | 30 | 0 |
| `expenses` | 30 | 0 |
| `gcal_status` | 30 | 0 |
| `gcal_accounts` | 30 | 0 |
| `workmode_bootstrap` | 30 | 0 |
| `visit_prep` | 30 | 0 |
| `family_members` | 30 | 0 |
| `family_alerts` | 30 | 0 |
| `family_arrivals` | 30 | 0 |
| `ambient_sessions` | 30 | 0 |
| `ambient_daily_report` | 30 | 0 |
| `meeting_notes` | 30 | 0 |
| `sms_pending` | 30 | 0 |
| `drive_files` | 30 | 0 |
| `mac_status` | 30 | 0 |
| `mac_connected` | 30 | 0 |
| `contacts_count` | 30 | 0 |
| `location_context` | 30 | 0 |
| `parking_last` | 30 | 0 |
| `places_recent` | 30 | 0 |
| `attendance_history` | 30 | 0 |
| `health_status` | 30 | 0 |
| `emotional_state` | 30 | 0 |
| `emergency_contacts` | 30 | 0 |
| `medications` | 30 | 0 |
| `office_room_pulse` | 30 | 0 |
| `office_eod_wrap` | 30 | 0 |
| `office_rooms` | 30 | 0 |
| `office_supplies` | 30 | 0 |
| `office_colleagues` | 30 | 0 |
| `office_thanks_nudge` | 30 | 0 |
| `office_silence_radar` | 30 | 0 |
| `office_timezone_fatigue` | 30 | 0 |
| `office_manager_lens` | 30 | 0 |
| `office_expertise_finder` | 30 | 0 |
| `translate` | 30 | 0 |
| `chat_light` | 30 | 0 |
| `files_upload` | 30 | 0 |
| `document_analysis` | 30 | 0 |

Observed improvement:

- The earlier 2026-04-26 baseline was 50 calls with 82% hit rate and 0 errors.
- The 2026-05-06 backend regression matrix is 1380 safe checks with 100% transport/API pass rate.
- This does not mean every product decision is perfect; it means the safe API surface tested here is repeatable and stable.

## Remaining Gaps

These are intentionally not treated as complete just because the safe regression matrix passed:

| Gap | Why not fully tested yet | Required safe test setup |
|---|---|---|
| Real phone calls | Would call real recipients | Twilio sandbox number or dedicated test restaurant/contact |
| Real email send | Could email real people | Dummy inbox + send assertion |
| LINE / Telegram push | Could notify real accounts | Test bot/user only |
| Emergency escalation | Could alarm contacts | Dummy emergency contact channel |
| Voice STT on physical phone | Needs human speaking into device | Manual script with fixed phrases |
| File picker UX | Needs human selecting real files | Manual UI checklist or XCTest UI target |
| HealthKit live anomalies | Needs real sensor stream | Simulated HealthKit fixture or dedicated test mode |

## Recommendation

For partner/demo usage:

1. Use the current build for document analysis demos.
2. Demo with PDF/DOCX/TXT/MD files that are safe to upload to the VPS.
3. Keep `TEST_REPORTS.md` and `alfred_30x_test_report.json` together as the current proof bundle.
4. Before claiming external automation is production-ready, create dummy-channel tests for calls, email, LINE, Telegram, and emergency flows.
