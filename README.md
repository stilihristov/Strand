# Strand 

**An algorithmic approach to subterranean urbanism in a desertified Northern Italy.**

![Sub-Terra Settlement Axonometric](images/settlement_axo.jpg)

## 🌍 The Project
**Location:** Pavia, Po Valley, Italy  
**Year:** 2079  
**Concept:** Entomo-Agriculture & Subterranean Living

By 2079, the once-fertile Po Valley has succumbed to hyper-aridity, turning the region into a steppe[cite: 26, 40]. "Sub-Terra" proposes a survivalist evolution of the region's historical silk industry. [cite_start]Instead of farming silkworms for luxury, the settlement farms resilient insects (crickets, mealworms) for protein.

To survive surface temperatures reaching 50°C, the architecture colonizes the subsurface.Living quarters are buried 3 meters deep, utilizing the earth's thermal mass to maintain a stable 18°C, while "Solar Chimneys" and "Lightcores" pierce the crust to provide passive ventilation and natural light.

## 💻 Why GitHub for Architecture?
Architecture is often seen as a static visual discipline, but *Strand** treats the city as a biological algorithm. I am using GitHub to manage the **Python scripts** that generate the settlement's morphology.

This repository hosts the generative logic used in Rhino/Grasshopper.

### 🐍 Key Script: `cluster_logic.py`
The core of this repository is a Python script for Rhino/Grasshopper that automates the layout of the underground clusters.

**Recent Updates:**
* **Cluster Logic:** Implemented a `Block` class to manage spatial relationships between Living, Gathering, and Production units.
* **Cellular Drainage:** Shifted from a monolithic drainage layer to a per-cluster "cellular" system. This allows the settlement to expand organically over time without compromising the waterproofing of existing sectors.
* **Boolean Union Logic:** Added algorithms to group curves by "historical era" and generate the necessary protective gravel trenches between them.

## 📸 Visualization

### The Settlement System
The project operates as a closed-loop metabolic system. The isometric view below shows the relationship between the subterranean dwelling and the surface infrastructure.
![Sub-Terra Axonometric](images/settlement_axo.jpg)

### Surface Conditions (Day)
The surface is harsh and arid. The steel-clad Solar Chimneys are the only visible sign of the life teeming below, acting as thermal engines to drive ventilation.
![Surface Day View](images/outside_day.jpg)

### Surface Conditions (Night)
Life emerges at night. When temperatures drop, the Lightcores—which channel sunlight down during the day—become lanterns, illuminating the communal spaces above ground.
![Surface Night View](images/outside_night.jpg)

## 🛠️ Tech Stack
* **Rhino 7 / 8** (Geometry Engine)
* **Grasshopper** (Parametric Environment)
* **Python (RhinoScriptSyntax)** (Scripting Logic)

---
*Project by [Your Name]*
