# Design Document

## Overview

This design outlines a comprehensive documentation enhancement for the StreamViewer project. The documentation will be structured in two main parts:

1. **Project Architecture Documentation** - A high-level guide explaining the overall system design, component relationships, and data flow
2. **Renderer Development Guide** - A practical, tutorial-style guide for developers who want to create custom visualization renderers

The documentation will be created as markdown files within the existing `docs/` directory structure, building upon the current documentation framework that uses mkdocs.

## Architecture

### Documentation Structure

The new documentation will integrate with the existing docs structure:

```
docs/
├── README.md (existing - entry point)
├── outline/
│   ├── overview.md (existing)
│   ├── extending.md (existing - to be enhanced)
│   ├── customizing.md (existing)
│   └── integrating.md (existing)
├── modules/
│   ├── renderers/
│   │   ├── overview.md (existing)
│   │   ├── architecture.md (NEW - detailed architecture)
│   │   └── development-guide.md (NEW - step-by-step tutorial)
│   └── widgets/
│       └── development-guide.md (NEW - widget creation guide)
└── img/ (existing - for diagrams)
```

### Content Organization

#### 1. Architecture Documentation (`docs/modules/renderers/architecture.md`)

This document will provide a comprehensive technical overview:

- **System Overview**: High-level explanation of StreamViewer's purpose and design philosophy
- **Component Architecture**: Detailed breakdown of the four main modules (applications, data, renderers, widgets)
- **Data Flow Diagram**: Visual representation showing LSL streams → data sources → buffers → renderers → display
- **Renderer Class Hierarchy**: Explanation of the cooperative inheritance pattern with diagrams
- **Plugin System**: How the resolver pattern discovers and loads plugins at runtime
- **Buffer Management**: How different buffer types handle streaming data

#### 2. Renderer Development Guide (`docs/modules/renderers/development-guide.md`)

This will be a practical, tutorial-style guide structured as:

- **Quick Start**: Minimal example to get developers started immediately
- **Understanding the Base Classes**: Explanation of RendererFormatData and RendererBaseDisplay
- **Step-by-Step Tutorial**: Creating a simple renderer from scratch
  - Setting up the file structure
  - Implementing required methods
  - Handling data updates
  - Testing the renderer
- **Advanced Topics**:
  - Working with different buffer types
  - Implementing auto-scaling
  - Performance optimization for real-time rendering
  - Handling multiple data sources
- **Real-World Examples**: Annotated code from LinePG and other existing renderers
- **Common Patterns**: Best practices observed across existing renderers

#### 3. Widget Development Guide (`docs/modules/widgets/development-guide.md`)

Companion guide for creating control panel widgets:

- **Widget-Renderer Relationship**: How widgets connect to renderers via signals/slots
- **Creating a Basic Control Panel**: Step-by-step tutorial
- **Common UI Controls**: Examples of sliders, checkboxes, combo boxes
- **Settings Persistence**: Using QSettings to save/restore configuration
- **Integration**: How widgets are discovered and loaded by the application

## Components and Interfaces

### Documentation Components

#### Architecture Document

**Purpose**: Provide comprehensive understanding of system design

**Key Sections**:
- Introduction and design philosophy
- Module breakdown with responsibilities
- Data flow visualization (Mermaid diagrams)
- Class hierarchy diagrams
- Plugin discovery mechanism
- Buffer types and their use cases

**Target Audience**: Developers new to the project, contributors wanting to understand the architecture

#### Renderer Development Guide

**Purpose**: Enable developers to create custom renderers quickly

**Key Sections**:
- Prerequisites and setup
- Minimal working example (< 50 lines)
- Required method implementations:
  - `__init__()` - initialization and parameter handling
  - `reset_renderer(reset_channel_labels)` - rebuild visualization
  - `update_visualization(data, timestamps)` - render new data
  - `reset_buffers()` - configure data buffers
- Property decorators and Qt slots
- Integration with gui_kwargs for settings persistence
- Testing and debugging strategies

**Target Audience**: Developers creating custom visualizations

#### Widget Development Guide

**Purpose**: Enable developers to create control panels for their renderers

**Key Sections**:
- IControlPanel base class overview
- Creating custom widgets
- Signal/slot connections to renderer
- Layout management with QGridLayout
- Settings persistence with QSettings
- Common patterns from existing widgets

**Target Audience**: Developers who have created a renderer and need UI controls

### Code Examples

Each guide will include multiple code examples:

1. **Minimal Renderer** (30-40 lines): Simplest possible implementation
2. **Annotated LinePG**: Walkthrough of existing complex renderer
3. **Custom Control Panel**: Example widget with common controls
4. **Plugin Package Structure**: How to organize and distribute plugins

### Diagrams

Visual aids to be created using Mermaid syntax:

1. **Data Flow Diagram**: LSL → DataSource → Buffer → Renderer → Display
2. **Class Hierarchy**: Showing cooperative inheritance pattern
3. **Plugin Discovery**: How resolvers search for and load plugins
4. **Renderer Lifecycle**: Initialization → Reset → Update cycle

## Data Models

### Documentation Metadata

Each documentation file will include:

```yaml
---
title: Document Title
description: Brief description
audience: [developers, integrators, contributors]
difficulty: [beginner, intermediate, advanced]
related: [list of related doc files]
---
```

### Code Example Structure

Code examples will follow this pattern:

```python
# Filename: example_renderer.py
# Purpose: Brief description
# Requirements: List of dependencies

# Imports
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer

# Implementation
class ExampleRenderer(RendererDataTimeSeries, PGRenderer):
    """
    Docstring explaining purpose and usage
    """
    
    # Class variables
    gui_kwargs = {...}  # For settings persistence
    
    def __init__(self, **kwargs):
        # Initialization logic
        pass
    
    def reset_renderer(self, reset_channel_labels=True):
        # Rebuild visualization
        pass
    
    def update_visualization(self, data, timestamps):
        # Render new data
        pass
```

## Error Handling

### Documentation Quality Checks

- **Code Examples**: All code examples must be tested and verified to work
- **Links**: Internal links must be validated to ensure they point to existing files
- **Consistency**: Terminology must be consistent across all documentation
- **Completeness**: All required methods and parameters must be documented

### Common Pitfalls Section

Each guide will include a "Common Pitfalls" section addressing:

- Forgetting to call `super().__init__()` in cooperative inheritance
- Not implementing all required abstract methods
- Incorrect buffer type selection
- Performance issues with real-time rendering
- Settings persistence problems
- Plugin discovery issues (naming conventions, file structure)

## Testing Strategy

### Documentation Validation

1. **Code Example Testing**:
   - Create a test script that runs all code examples
   - Verify examples produce expected output
   - Test with different Python versions (3.8+)

2. **Link Validation**:
   - Use mkdocs build process to check for broken links
   - Verify all cross-references resolve correctly

3. **User Testing**:
   - Have a developer unfamiliar with the codebase follow the tutorial
   - Collect feedback on clarity and completeness
   - Iterate based on feedback

### Example Renderer Tests

The development guide will include a minimal test renderer that can be used to verify:
- Plugin discovery works correctly
- Renderer integrates with lsl_viewer application
- Settings persistence functions properly
- Control panel widgets connect correctly

## Implementation Notes

### Existing Documentation Enhancement

The current `docs/outline/extending.md` file provides a brief overview of the plugin system. The new documentation will:

- Expand on the existing content with detailed examples
- Add step-by-step tutorials that were previously missing
- Provide comprehensive API documentation for base classes
- Include visual diagrams to clarify architecture

### Integration with mkdocs

The documentation will leverage the existing mkdocs setup:

- Use the material theme features (admonitions, tabs, code highlighting)
- Add navigation entries in `mkdocs.yml` for new pages
- Use Mermaid plugin for diagrams
- Ensure mobile-responsive formatting

### Documentation Style

- **Tone**: Technical but approachable, assuming Python/Qt knowledge
- **Structure**: Progressive disclosure - simple examples first, complexity later
- **Code Style**: Follow PEP 8, include type hints where helpful
- **Examples**: Real-world scenarios, not just toy examples

## Design Decisions and Rationales

### Decision 1: Enhance Existing Structure vs. Complete Rewrite

**Decision**: Enhance and expand existing documentation rather than replace it

**Rationale**: 
- Current structure is sound and uses mkdocs effectively
- Existing overview and extending docs provide good foundation
- Users may have bookmarked existing pages
- Incremental improvement is less disruptive

### Decision 2: Separate Architecture and Tutorial Docs

**Decision**: Create distinct documents for architecture overview and development tutorial

**Rationale**:
- Different audiences have different needs
- Architecture doc serves as reference for understanding system design
- Tutorial doc serves as practical guide for implementation
- Separation allows each to be comprehensive without overwhelming readers

### Decision 3: Focus on Renderers First, Widgets Second

**Decision**: Prioritize renderer documentation, with widgets as secondary

**Rationale**:
- Renderers are the primary extension point
- Widget creation typically follows renderer creation
- Most developers will create renderers; fewer will need custom widgets
- Generic control panel works for many use cases

### Decision 4: Include Minimal Working Examples

**Decision**: Start each guide with a minimal (< 50 lines) working example

**Rationale**:
- Developers want to see results quickly
- Minimal examples clarify essential requirements
- Can be used as templates for new implementations
- Reduces barrier to entry for new contributors

### Decision 5: Use Mermaid for Diagrams

**Decision**: Create diagrams using Mermaid syntax embedded in markdown

**Rationale**:
- Diagrams live in version control as text
- Easy to update and maintain
- Renders automatically in mkdocs
- No external image editing tools required
- Consistent styling across documentation
