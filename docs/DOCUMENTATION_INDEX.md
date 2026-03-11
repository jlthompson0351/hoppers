# Documentation Index

This index organizes the project documentation by category. Use this to find relevant information quickly.

## 🏗️ Core Architecture & Implementation
*   [Architecture.md](Architecture.md) - High-level system design and component interaction.
*   [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md) - Detailed breakdown of the current code structure and logic.
*   [SRS.md](SRS.md) - Software Requirements Specification.
*   [RiskRegister.md](RiskRegister.md) - Project risks and mitigation strategies.

## 🎛️ Hardware Reference
*   [24b8vin_Hardware_Reference.md](24b8vin_Hardware_Reference.md) - Specifications for the 8-channel ADC HAT.
*   [24b8vin_Implementation_Notes.md](24b8vin_Implementation_Notes.md) - Notes on implementing the ADC driver.
*   [24b8vin_Quick_Reference.md](24b8vin_Quick_Reference.md) - Quick lookup for ADC commands.
*   [MegaIND_Capabilities_Diagram.md](MegaIND_Capabilities_Diagram.md) - Visual guide to the Industrial I/O HAT.
*   [MegaIND_Settings_SPEC.md](MegaIND_Settings_SPEC.md) - Configuration specification for the MegaIND board.
*   [MegaIND_QuickRef.md](MegaIND_QuickRef.md) - Quick lookup for MegaIND commands.
*   [WiringAndCommissioning.md](WiringAndCommissioning.md) - Guide for wiring load cells and PLC connections.
*   [HARDWARE_DEEP_RESEARCH_FINDINGS.md](HARDWARE_DEEP_RESEARCH_FINDINGS.md) - Research notes on hardware selection.

## ⚖️ Calibration & Zeroing
*   [CalibrationProcedure.md](CalibrationProcedure.md) - Step-by-step guide for calibrating the scale.
*   [CALIBRATION_CURRENT_STATE.md](CALIBRATION_CURRENT_STATE.md) - Snapshot of the current calibration parameters.
*   [ZERO_TRACKING_OPERATOR_GUIDE.md](ZERO_TRACKING_OPERATOR_GUIDE.md) - Operator instructions for the zero-tracking system.
*   [ZERO_TRACKING_CHANGELOG.md](ZERO_TRACKING_CHANGELOG.md) - History of changes to the zero-tracking logic.
*   [DRIFT_COMPENSATION_DIAGRAM.md](DRIFT_COMPENSATION_DIAGRAM.md) - Visual explanation of drift compensation.
*   [ZERO_VS_TARE_FIX.md](ZERO_VS_TARE_FIX.md) - Explanation of the difference between Zero and Tare.
*   [PLC_OUTPUT_DRIFT_ROOT_CAUSE.md](PLC_OUTPUT_DRIFT_ROOT_CAUSE.md) - Analysis of PLC signal drift issues.

## 🚀 Operations & Deployment
*   [CONNECTION_GUIDE.md](CONNECTION_GUIDE.md) - How to connect to the Pi (SSH, Web UI).
*   [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md) - Log of deployments to the production Pi.
*   [FLEET_INVENTORY.md](FLEET_INVENTORY.md) - List of deployed devices and their details.
*   [HDMI_KIOSK_RUNBOOK.md](HDMI_KIOSK_RUNBOOK.md) - Setup guide for the touchscreen kiosk mode.
*   [MaintenanceAndTroubleshooting.md](MaintenanceAndTroubleshooting.md) - Common issues and fixes.
*   [SET_WEIGHT_PERSISTENCE_RUNBOOK.md](SET_WEIGHT_PERSISTENCE_RUNBOOK.md) - Durable set-weight schema, migrations, and rollout checks.
*   [JOB_COMPLETION_WEBHOOK_RUNBOOK.md](JOB_COMPLETION_WEBHOOK_RUNBOOK.md) - Completed-job webhook payloads, outbox retry behavior, and test procedure.
*   [SD_CARD_DISASTER_RECOVERY_RUNBOOK.md](SD_CARD_DISASTER_RECOVERY_RUNBOOK.md) - Procedures for recovering from SD card failure.

## 🧪 Testing & Verification
*   [TestPlan.md](TestPlan.md) - Master test plan.
*   [QUICK_START_HARDWARE_TEST.md](QUICK_START_HARDWARE_TEST.md) - Rapid hardware verification steps.
*   [HardwareTestReadiness_TODAY.md](HardwareTestReadiness_TODAY.md) - Daily readiness check.
*   [PLC_OUTPUT_VERIFICATION.md](PLC_OUTPUT_VERIFICATION.md) - Verification results for PLC analog output.
*   [AUTO_ARMED_OUTPUT_CHANGE.md](AUTO_ARMED_OUTPUT_CHANGE.md) - Documentation on auto-arming logic changes.

## 📦 Archives & Logs (Candidates for Cleanup)
*   `*_backup_*.csv` - Old backup files.
*   `shift_log_*.txt` - Raw shift logs.
*   `hour_log_*.txt` - Raw hourly logs.
*   `pre_retrain_backup_*.md` - Backup before retraining.
*   `TODAY_SUMMARY.md` - Daily summaries (rename to date-specific if keeping).
*   `DOCUMENTATION_UPDATE_SUMMARY.md` - Meta-doc about updates.

## 📝 Meta
*   [README_DOCS.md](README_DOCS.md) - Guide to this documentation folder.
*   [TODO_BACKLOG.md](TODO_BACKLOG.md) - Active implementation backlog and rollout follow-ups.
