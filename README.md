# Gimme VMs 🚀

`gimme-vms` is a lightweight, automated Python script designed to bulk-provision Google Compute Engine (GCE) virtual machines (VMs). It is specifically tailored for provisioning high-performance GPU instances (like NVIDIA H100s via A3 machine shapes) but can be used for any standard Compute Engine VM.

The script checks for already running or pending instances matching a specific naming pattern in a zone and only requests the difference needed to reach your target capacity—limiting how many VMs are requested per run to avoid exceeding quotas or running into sudden billing spikes.

---

## Features

- **Smart Capacity Check**: Queries existing instances matching a pattern (e.g. `h100-test-###`) before provisioning, ensuring you don't over-provision.
- **Bulk Insert Support**: Uses Google Cloud's official native bulk insertion APIs (`BulkInsertInstanceResource`) for rapid, concurrent VM launching.
- **Instance Template or Inline Specs**: Provision via an existing Instance Template or declare inline VM properties (Machine Type, Disk, Network, Spot/Preemptible status) directly in the code.
- **Preemption & Spot VM Support**: Easily configure VMs as Preemptible or Spot to optimize cost.
- **Safe Run Limits**: Limit the maximum number of VMs provisioned per run (e.g., maximum 4 at a time) to respect GCP quotas and control rate-of-spend.

---

## Prerequisites

Before running the provisioner, make sure you have completed the following:

1. **Google Cloud Project**: A GCP Project with billing enabled.
2. **Compute Engine API**: Ensure the Compute Engine API is enabled in your project.
3. **Quotas**: Ensure your project has sufficient GPU/CPU/IP address quotas in the target zone (e.g., `a3-highgpu-8g` requires specific TPU/GPU quotas).
4. **Authentication**: Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) and set up Application Default Credentials (ADC):
   ```bash
   gcloud auth application-default login
   ```

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gimme-vms.git
   cd gimme-vms
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

All configuration is managed inside the top section of [main.py](file:///Users/wellsmike/Downloads/gimme-vms/main.py). Open the file and adjust these parameters:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROJECT_ID` | Your GCP Project ID (reads `GOOGLE_CLOUD_PROJECT` env var or defaults to a fallback string). | `GOOGLE_CLOUD_PROJECT` / `"YOUR_GCP_PROJECT_ID"` |
| `ZONE` | The GCP zone where VMs will be deployed. | `"us-central1-a"` |
| `NAME_PATTERN` | The name pattern for instances. `#` is replaced with numeric digits. | `"h100-test-###"` |
| `TARGET_COUNT` | Total number of running/pending instances you want to maintain. | `8` |
| `MAX_PER_RUN` | Max number of instances to spin up in a single execution. | `4` |
| `USE_TEMPLATE` | Set to `True` to use a GCP Instance Template; `False` to define VM properties inline. | `False` |
| `INSTANCE_TEMPLATE` | Name of the instance template (used if `USE_TEMPLATE = True`). | `"h100-test-template"` |
| `MACHINE_TYPE` | Machine shape (used if `USE_TEMPLATE = False`). | `"a3-highgpu-8g"` |
| `BOOT_DISK_IMAGE` | The operating system image path for the boot disk. | Debian 12 |
| `BOOT_DISK_SIZE_GB`| Boot disk size in Gigabytes. | `100` |
| `BOOT_DISK_TYPE` | Boot disk disk type (e.g. `pd-standard`, `pd-balanced`, `pd-ssd`). | `"pd-balanced"` |
| `NETWORK` | Network resource path. | `"global/networks/default"` |
| `SUBNETWORK` | Optional subnetwork resource path. | `""` |
| `ASSIGN_EXTERNAL_IP`| Assign an ephemeral public external IP address. | `True` |
| `PREEMPTIBLE` | Use Preemptible VM model. | `False` |
| `SPOT` | Use Spot VM model. | `False` |

---

## Usage

Set your GCP Project ID environment variable:
```bash
export GOOGLE_CLOUD_PROJECT="your-actual-gcp-project-id"
```

Then run the provisioner:
```bash
python main.py
```

### Script Execution Logic:
1. Queries all VMs in `ZONE` matching the regular expression equivalent of `NAME_PATTERN` (e.g., `^h100-test-[0-9][0-9][0-9]$`).
2. Identifies instances that are active (status is `PROVISIONING`, `STAGING`, `RUNNING`, or `REPAIRING`).
3. Calculates `needed = TARGET_COUNT - current_active_count`.
4. Requests `min(needed, MAX_PER_RUN)` instances using the bulk insert API.
5. Blocks until the bulk insert operation completes or times out.

---

## License

This project is licensed under the [MIT License](LICENSE) (or choose your own license).
