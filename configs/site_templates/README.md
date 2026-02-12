# Site Configuration Templates

This directory contains reusable configuration templates for new site installations.

## Available Templates

### Standard Templates (Create as needed)

| Template Name | Hopper Type | Capacity | Use Case |
|---------------|-------------|----------|----------|
| `4leg_250lb_static.json` | 4-leg | 250 lb | Standard production hopper |
| `4leg_500lb_dynamic.json` | 4-leg | 500 lb | Filling hopper with conveyor |
| `2leg_500lb_static.json` | 2-leg | 500 lb | Smaller footprint hopper |
| `4leg_1000lb_static.json` | 4-leg | 1000 lb | Large capacity hopper |

## Template Structure

Each template should contain:

```json
{
  "_template_info": {
    "name": "template-name",
    "description": "When to use this template",
    "version": "1.0",
    "created": "YYYY-MM-DD"
  },
  
  "site": {
    "name": "[CUSTOMIZE]",
    "location": "[CUSTOMIZE]",
    "pi_ip": "[CUSTOMIZE]",
    "hostname": "[CUSTOMIZE]",
    "install_date": "[CUSTOMIZE]",
    "installer": "[CUSTOMIZE]",
    "contact": "[CUSTOMIZE]"
  },
  
  "hopper": {
    "type": "4-leg",
    "capacity_lb": 250,
    "load_cell_channels": [1, 2, 3, 4],
    "excitation_nominal_v": 10.0
  },
  
  "plc": {
    "type": "[CUSTOMIZE]",
    "output_mode": "0-10V",
    "scaling_lb_per_v": 25.0,
    "modbus_enabled": false
  },
  
  "signal_processing": {
    "ratiometric_enabled": true,
    "filter_type": "kalman",
    "kalman_q": 1.0,
    "kalman_r": 50.0,
    "stability_window": 25
  },
  
  "zero_tracking": {
    "enabled": true,
    "rate_lb_per_s": 0.1,
    "threshold_lb": 0.5
  },
  
  "calibration": {
    "status": "pending",
    "recommended_points": [0, 25, 50, 75, 100],
    "notes": "Calibrate after installation"
  }
}
```

## How to Use Templates

### 1. Select Appropriate Template
Choose based on:
- Number of load cells (2-leg vs 4-leg)
- Capacity (250, 500, 1000 lb)
- Application (static vs dynamic)

### 2. Create Site-Specific Config
```powershell
# Copy template
Copy-Item "4leg_250lb_static.json" "..\deployed\pi_192.168.1.100.json"
```

### 3. Customize Fields
Edit the copied file:
- Update all `[CUSTOMIZE]` fields
- Set correct IP address
- Adjust settings for site requirements

### 4. Deploy with Config
Use the `site-commissioning` skill to deploy.

## Creating New Templates

When you encounter a new hopper configuration:

1. Create a new template based on closest existing one
2. Update `_template_info` with description
3. Set default values appropriate for the configuration
4. Add to this README's template list
5. Test with a real installation

## Template vs Deployed

- **Templates** (`site_templates/`): Reusable starting points
- **Deployed** (`deployed/`): Actual configs for specific sites

Never deploy directly from templates - always copy and customize first.

## Calibration Notes

Templates include calibration structure but NOT calibration data.
Calibration is site-specific and must be performed on-site.

Recommended calibration points vary by capacity:
- 250 lb: 0, 50, 100, 150, 200, 250 lb
- 500 lb: 0, 100, 200, 300, 400, 500 lb
- 1000 lb: 0, 200, 400, 600, 800, 1000 lb
