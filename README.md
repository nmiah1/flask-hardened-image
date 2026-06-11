# **Flask Application Optimization & Hardening Guide**

This repository hosts a Python Flask web application structured around the **GOV.UK Frontend** asset ecosystem and engineered with secure identity integrations through **Authlib** and **Keycloak**.

The goal of this setup is to establish a clear, side-by-side architectural and image-size comparison between:

1. A traditional single-stage configuration using a Red Hat **UBI-Minimal** base image.  
2. An optimized, secure multi-stage build using a **Red Hat Hardened Image (hi)** runtime framework.

## **📋 Table of Contents**

1. [Project Directory Layout](#bookmark=id.uhnez2xfp819)  
2. [Image Architecture Comparison](#bookmark=id.sz2y8nw2rq3z)  
3. [Containerfile Implementations](#bookmark=id.kasus2o2n7nb)  
   * [Option A: UBI-Minimal (Single Stage)](#bookmark=id.6noc9xoghfd2)  
   * [Option B: Red Hat Hardened Image (Multi-Stage with lib64 fix)](#bookmark=id.g2ja8028s2lb)  
4. [Local Execution and Testing](#bookmark=id.ekn9f06nkcmt)  
5. [Scale-Out Mathematical Savings (10,000 Containers)](#bookmark=id.15rxrq3kb2zx)  
6. [Key Architectural Lessons](#bookmark=id.b1vwf2t8xvjk)

## **📂 Project Directory Layout**

To execute these builds smoothly without configuration cross-contamination, organize your root directory exactly as follows:

my-project/  
├── python-app/                      \# Core application folder  
│   ├── app.py                       \# Main Flask server  
│   ├── requirements.txt             \# App requirements (flask, authlib, requests, etc.)  
│   ├── keycloak\_admin.py            \# Keycloak integration helper  
│   ├── govuk\_assets.py              \# GOV.UK asset mapping helper  
│   ├── static/                      \# CSS/JS and static assets  
│   └── templates/                   \# Jinja2 layout templates  
├── Containerfile.minimal            \# Build recipe for Option A (UBI-Minimal)  
└── Containerfile.hardened           \# Build recipe for Option B (Red Hat Hardened)

## **📊 Image Architecture Comparison**

Local compilation of both images yields the following physical footprints and operating parameters:

| Metric | Option A: ubi-minimal | Option B: Red Hat Hardened Image |
| :---- | :---- | :---- |
| **Base / Builder Image** | ubi9/ubi-minimal:9.8-1780378819 | hi/python:3.14-builder \+ hi/python:latest |
| **Final Image Size** | **275 MB** | **199 MB** *(76 MB Space Saved / 28% reduction)* |
| **Build Pattern** | Single-Stage | Multi-Stage (Strict compilation isolation) |
| **Package Manager** | microdnf (Retained in production) | **None** (Completely stripped for security) |
| **System Binaries** | Shell utilities, compilation headers present | Micro-runtime stripped of non-execution tools |
| **CVE Attack Surface** | Broad OS footprint | Highly restricted (Only core python interpreter) |

## **🛠 Containerfile Implementations**

### **Option A: UBI-Minimal (Single-Stage)**

*File Location: ./Containerfile.minimal*

This configuration relies on installing the modern Python 3.14 package manager and execution environment directly onto the raw UBI-Minimal operating system layer.

FROM \[registry.access.redhat.com/ubi9/ubi-minimal:latest\](https://registry.access.redhat.com/ubi9/ubi-minimal:latest)

WORKDIR /app

\# Install Python 3.14 and its package manager, then clean dnf cache to save space  
RUN microdnf install \-y python3.14 python3.14-pip && \\  
    microdnf clean all

\# Copy and install dependencies  
COPY python-app/requirements.txt .  
RUN pip3.14 install \--no-cache-dir \-r requirements.txt

\# Copy application source  
COPY python-app/ /app/

EXPOSE 8080  
ENTRYPOINT \["python3.14", "/app/app.py"\]

### **Option B: Red Hat Hardened Image (Multi-Stage with lib64 fix)**

*File Location: ./Containerfile.hardened*

Because your application depends on **Authlib** (which builds compiled cryptography bindings) and **Werkzeug/Flask** (which relies on markupsafe speedup extensions), Python builds binary .so wheels.

Modern standard pip configurations send pure-Python packages to /usr/local/lib/python3.14/site-packages, but compile architectural binary wheels directly into **/usr/local/lib64/python3.14/site-packages**. Failing to copy both directories results in a ModuleNotFoundError: No module named 'markupsafe'.

This configuration resolves this by explicitly copying standard and 64-bit packages over from the builder.

\# \--- Stage 1: Build & Package Compilation \---  
FROM \[registry.access.redhat.com/hi/python:3.14-builder\](https://registry.access.redhat.com/hi/python:3.14-builder) AS builder

USER root  
WORKDIR /app

\# Compile dependencies directly using pip  
COPY python-app/requirements.txt .  
RUN pip install \--no-cache-dir \-r requirements.txt

\# Revert back to the unprivileged default user for build compliance  
USER ${CONTAINER\_DEFAULT\_USER}

\# \--- Stage 2: Hardened Minimal Deployment Runtime \---  
FROM \[registry.access.redhat.com/hi/python:latest\](https://registry.access.redhat.com/hi/python:latest)

\# CRITICAL RESOLUTION: Copy BOTH standard and 64-bit compiled binary directories  
COPY \--from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages  
COPY \--from=builder /usr/local/lib64/python3.14/site-packages /usr/local/lib64/python3.14/site-packages

\# Copy application files to runtime environment  
COPY python-app/ /app/

WORKDIR /app

EXPOSE 8080  
ENTRYPOINT \["python3", "/app/app.py"\]

## **🚀 Local Execution and Testing**

Because both images possess different default OS-level properties (such as Red Hat's strict health check timers and restricted non-root execution frameworks), use the following workflow to build and validate them locally.

### **1\. Execute Build Recipes**

podman build \-f Containerfile.minimal \-t flask-app:minimal .  
podman build \-f Containerfile.hardened \-t flask-app:hardened .

### **2\. Compare Sizes Side-by-Side**

podman images | grep flask-app

### **3\. Start Local Container Instances**

Since Red Hat base images define standard container health-checks that require custom configurations to resolve locally, use the \--no-healthcheck flag during verification to bypass local engine polling:

\# Run UBI-Minimal (Mapped to host port 8080\)  
podman run \-d \--name flask-minimal \--no-healthcheck \-p 8080:8080 localhost/flask-app:minimal

\# Run Hardened (Mapped to host port 8081\)  
podman run \-d \--name flask-hardened \--no-healthcheck \-p 8081:8080 localhost/flask-app:hardened

### **4\. Check Workload Statuses & Logs**

\# Confirm containers are safely active (Up)  
podman ps \-a

\# Access execution stream to check Flask console warnings  
podman logs flask-hardened

* Navigate to **http://localhost:8080** to browse your Minimal image container.  
* Navigate to **http://localhost:8081** to browse your Hardened image container.

## **📈 Scale-Out Mathematical Savings (10,000 Containers)**

Scaling an application across an enterprise Kubernetes/OpenShift fleet containing **10,000 container replicas** distributed across multiple clusters highlights the real value of a **76 MB** optimization:

### **1\. Global Registry & Node Disk Space Saved**

In a container ecosystem, layers are cached on physical host worker nodes. Assuming an environment with **2,000 unique worker nodes** across multiple clusters:

### **![][image1]2\. Network Traffic Eliminated Per Deployment**

Whenever a CI/CD pipeline pushes a code update to production, every node hosting the pod replica must pull down the modified layers. If you redeploy to a **2,000 node** cluster topology:

* ![][image2]**Production Advantage**: This significantly lowers cloud egress billing, minimizes registry bottlenecks during deployment, and speeds up cluster **Auto-Scaling (Time-to-Ready)**.

### **3\. RAM Footprint Optimization**

A hardened runtime completely eliminates the background memory overhead associated with running package managers (microdnf), system tracking hooks, and compilation libraries. If the hardened environment reduces the memory footprint by even **5 MB** per active replica:

## **![][image3]🛡 Key Architectural Lessons**

1. **Decoupled Security (Builder vs. Runtime)**: The final Hardened Image contains no package manager, no shell tools, and no compilers. This drastically lowers your vulnerability profile (CVE counts) because attackers cannot use internal operating system components to install or run exploit scripts.  
2. **Multi-Arch Binary Distribution**: If an application requires compiled C-extension cryptography or formatting libraries, a multi-stage copying strategy *must* copy both /usr/local/lib and /usr/local/lib64 directories to preserve architecture-dependent binary wheels.  
3. **Execution as Non-Root**: The Hardened Python runtime strictly runs as an unprivileged user (USER 1001). Your code must never attempt write operations to root-restricted directories at runtime, ensuring your security policies align with zero-trust container standards.
