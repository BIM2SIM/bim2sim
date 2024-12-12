# How to Contribute?


## Version Control Guidelines

### Versioning Rules

When pushing changes to development, always update the version number in `pyproject.toml` according to the following semantic versioning guidelines:

#### Current Status
- Project is in alpha phase
- Version format: `0.x.x`
- Transition to `1.0.0` will mark exit from alpha phase

#### Version Number Components

1. **Major Version** (`0.x.x`)
   - Reserved for breaking changes
   - Currently locked at `0` during alpha phase
   - Increment to `1` will indicate production-ready release

2. **Minor Version** (`x.1.x`)
   - Increment for new features or significant changes
   - Examples:
     - Adding new plugins
     - Major architectural changes (e.g., replacing cached properties with attribute system)
     - Functionality enhancements

3. **Patch Version** (`x.x.1`)
   - Increment for bug fixes and minor improvements
   - No significant feature changes

### Implementation

1. Create your feature branch
2. Update version in `pyproject.toml`
3. Commit changes
4. Push to development

### Example
```toml
# Before: version = "0.1.0"
# After adding new plugin: version = "0.2.0"
# After bug fix: version = "0.2.1"
```
---
**Note**: Always commit version changes along with your code changes in the same branch.

## What do I have to do, when I want to use bim2sim for other simulation tools?

### Which files/functions needs to be adapted/created?
- link to plugintemplate

### What is stored in tasks?

### What is stored in projects?

### What is stored in plugins?

### What is stored in playgrounds?

