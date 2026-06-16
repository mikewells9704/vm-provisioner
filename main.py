import os
import re
# pyrefly: ignore [missing-import]
from google.cloud import compute_v1

# =====================================================================
# CONFIGURATION ATTRIBUTES (Tailored for H100 / A3 VMs by default)
# =====================================================================
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "YOUR_GCP_PROJECT_ID")
ZONE = "us-central1-a"
NAME_PATTERN = "h100-test-###"
TARGET_COUNT = 8
MAX_PER_RUN = 4

# How do you want to define the VM specification?
# Set USE_TEMPLATE = True to use an existing Instance Template.
# Set USE_TEMPLATE = False to use the inline properties below.
USE_TEMPLATE = False

# Option A: Instance Template (used if USE_TEMPLATE is True)
INSTANCE_TEMPLATE = "h100-test-template"

# Option B: Inline Properties (used if USE_TEMPLATE is False)
# - Machine Type (defines family, type, and shape/size, e.g. "a3-highgpu-8g" for H100)
MACHINE_TYPE = "a3-highgpu-8g"

# - Boot Disk Settings
BOOT_DISK_IMAGE = "projects/debian-cloud/global/images/family/debian-12"
BOOT_DISK_SIZE_GB = 100
BOOT_DISK_TYPE = "pd-balanced"  # e.g., pd-standard, pd-balanced, pd-ssd

# - Network Settings
NETWORK = "global/networks/default"
SUBNETWORK = ""  # Optional, e.g., "regions/us-central1/subnetworks/my-subnet"
ASSIGN_EXTERNAL_IP = True  # Assign ephemeral public external IP?

# - Scheduling (Preemptible / Spot)
PREEMPTIBLE = False
SPOT = False
# =====================================================================

def run_provisioner():
    instances_client = compute_v1.InstancesClient()
    
    # 1. Convert naming pattern (e.g. n4-test-###) to regex (e.g. ^n4-test-[0-9][0-9][0-9]$)
    escaped_pattern = re.escape(NAME_PATTERN)
    escaped_pattern = escaped_pattern.replace(r'\#', '[0-9]')
    regex_pattern = f"^{escaped_pattern}$"
    
    # 2. Query existing instances matching the pattern using server-side filtering
    filter_expr = f'name eq "{regex_pattern}"'
    print(f"Checking existing instances in {ZONE} matching filter '{filter_expr}'...")
    
    list_req = compute_v1.ListInstancesRequest(
        project=PROJECT_ID,
        zone=ZONE,
        filter=filter_expr
    )
    
    existing_instances = list(instances_client.list(request=list_req))
    
    # Filter for running or pending instances (PROVISIONING, STAGING, RUNNING, REPAIRING)
    running_or_pending = [
        inst for inst in existing_instances 
        if inst.status in ("PROVISIONING", "STAGING", "RUNNING", "REPAIRING")
    ]
    current_count = len(running_or_pending)
    existing_names = [inst.name for inst in running_or_pending]
    
    print(f"Found {current_count} running or pending matching instances: {existing_names}")
    
    if current_count >= TARGET_COUNT:
        print("Target count already met. Nothing to do.")
        return
        
    # 3. Calculate how many to request in this run
    needed = TARGET_COUNT - current_count
    request_count = min(needed, MAX_PER_RUN)
    
    print(f"Provisioning {request_count} more VM(s) (target: {TARGET_COUNT}, current: {current_count})...")
    
    # 4. Build bulk insert resource
    if USE_TEMPLATE:
        print(f"Using instance template: {INSTANCE_TEMPLATE}")
        template_path = f"projects/{PROJECT_ID}/global/instanceTemplates/{INSTANCE_TEMPLATE}"
        bulk_insert_resource = compute_v1.BulkInsertInstanceResource(
            count=request_count,
            min_count=request_count,
            name_pattern=NAME_PATTERN,
            source_instance_template=template_path
        )
    else:
        print(f"Using inline properties (Machine Type: {MACHINE_TYPE}, Image: {BOOT_DISK_IMAGE})")
        # Build boot disk configuration
        initialize_params = compute_v1.AttachedDiskInitializeParams(
            source_image=BOOT_DISK_IMAGE,
            disk_size_gb=BOOT_DISK_SIZE_GB,
            disk_type=BOOT_DISK_TYPE
        )
        boot_disk = compute_v1.AttachedDisk(
            boot=True,
            auto_delete=True,
            type_="PERSISTENT",
            initialize_params=initialize_params
        )

        # Build network interface configuration
        network_interface = compute_v1.NetworkInterface(
            network=NETWORK
        )
        if SUBNETWORK:
            network_interface.subnetwork = SUBNETWORK
        
        if ASSIGN_EXTERNAL_IP:
            access_config = compute_v1.AccessConfig(
                name="External NAT",
                type_="ONE_TO_ONE_NAT",
                network_tier="PREMIUM"
            )
            network_interface.access_configs = [access_config]

        # Build scheduling configuration
        scheduling = compute_v1.Scheduling()
        if SPOT:
            scheduling.provisioning_model = "SPOT"
            scheduling.preemptible = True
        elif PREEMPTIBLE:
            scheduling.preemptible = True

        # Build reservation affinity (default to ANY_RESERVATION so instances automatically link)
        reservation_affinity = compute_v1.ReservationAffinity(
            consume_reservation_type="ANY_RESERVATION"
        )

        # Combine all into InstanceProperties
        instance_properties = compute_v1.InstanceProperties(
            machine_type=MACHINE_TYPE,
            disks=[boot_disk],
            network_interfaces=[network_interface],
            scheduling=scheduling,
            reservation_affinity=reservation_affinity
        )

        bulk_insert_resource = compute_v1.BulkInsertInstanceResource(
            count=request_count,
            min_count=request_count,
            name_pattern=NAME_PATTERN,
            instance_properties=instance_properties
        )
    
    # 5. Execute bulk insert
    try:
        operation = instances_client.bulk_insert(
            project=PROJECT_ID,
            zone=ZONE,
            bulk_insert_instance_resource=bulk_insert_resource
        )
    except TypeError:
        # Fallback for older python client versions
        operation = instances_client.bulk_insert(
            project=PROJECT_ID,
            zone=ZONE,
            bulk_insert_instance_resource_resource=bulk_insert_resource
        )
        
    print(f"Bulk insert operation {operation.name} started. Waiting for completion...")
    operation.result(timeout=60)
    print("Successfully provisioned new VM(s)!")

# For local script execution
if __name__ == "__main__":
    try:
        run_provisioner()
    except Exception as e:
        print(f"Error: {e}")
