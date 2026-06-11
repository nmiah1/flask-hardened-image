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

```
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

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
```

### **Option B: Red Hat Hardened Image (Multi-Stage with lib64 fix)**

*File Location: ./Containerfile.hardened*

Because your application depends on **Authlib** (which builds compiled cryptography bindings) and **Werkzeug/Flask** (which relies on markupsafe speedup extensions), Python builds binary .so wheels.

Modern standard pip configurations send pure-Python packages to /usr/local/lib/python3.14/site-packages, but compile architectural binary wheels directly into **/usr/local/lib64/python3.14/site-packages**. Failing to copy both directories results in a ModuleNotFoundError: No module named 'markupsafe'.

This configuration resolves this by explicitly copying standard and 64-bit packages over from the builder.

```
\# \--- Stage 1: Build & Package Compilation \---  
FROM https://registry.access.redhat.com/hi/python:3.14-builder AS builder

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
```

## **🚀 Local Execution and Testing**

Because both images possess different default OS-level properties (such as Red Hat's strict health check timers and restricted non-root execution frameworks), use the following workflow to build and validate them locally.

### **1\. Execute Build Recipes**
```
podman build \-f Containerfile.minimal \-t flask-app:minimal .  
podman build \-f Containerfile.hardened \-t flask-app:hardened .
```
### **2\. Compare Sizes Side-by-Side**
```
podman images | grep flask-app
```
### **3\. Start Local Container Instances**

Since Red Hat base images define standard container health-checks that require custom configurations to resolve locally, use the \--no-healthcheck flag during verification to bypass local engine polling:

\# Run UBI-Minimal (Mapped to host port 8080\)  
```
podman run \-d \--name flask-minimal \--no-healthcheck \-p 8080:8080 localhost/flask-app:minimal
```
\# Run Hardened (Mapped to host port 8081\)  
```
podman run \-d \--name flask-hardened \--no-healthcheck \-p 8081:8080 localhost/flask-app:hardened
```
### **4\. Check Workload Statuses & Logs**

\# Confirm containers are safely active (Up)  
```
podman ps \-a
```
\# Access execution stream to check Flask console warnings  
```
podman logs flask-hardened
```
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

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>
