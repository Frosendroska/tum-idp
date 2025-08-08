#!/bin/bash

# R2 Benchmark Test Script
# This script tests the basic functionality of the benchmark implementation

set -e

echo "🧪 Testing R2 Benchmark Implementation"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}❌ $message${NC}"
    else
        echo -e "${YELLOW}⚠️  $message${NC}"
    fi
}

# Check if Go is installed
check_go() {
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        print_status "PASS" "Go is installed: $GO_VERSION"
    else
        print_status "FAIL" "Go is not installed"
        exit 1
    fi
}

# Check if Python is installed
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_status "PASS" "Python3 is installed: $PYTHON_VERSION"
    else
        print_status "FAIL" "Python3 is not installed"
        exit 1
    fi
}

# Check if required Python packages are available
check_python_packages() {
    local missing_packages=()
    
    for package in pandas matplotlib seaborn numpy pyarrow; do
        if ! python3 -c "import $package" &> /dev/null; then
            missing_packages+=($package)
        fi
    done
    
    if [ ${#missing_packages[@]} -eq 0 ]; then
        print_status "PASS" "All required Python packages are installed"
    else
        print_status "WARN" "Missing Python packages: ${missing_packages[*]}"
        echo "   Run: pip install -r requirements.txt"
    fi
}

# Test Go module
test_go_module() {
    echo "📦 Testing Go module..."
    
    if [ -f "go.mod" ]; then
        print_status "PASS" "go.mod file exists"
        
        # Try to download dependencies
        if go mod download &> /dev/null; then
            print_status "PASS" "Go dependencies downloaded successfully"
        else
            print_status "FAIL" "Failed to download Go dependencies"
            return 1
        fi
        
        # Try to build the binaries
        echo "🔨 Building binaries..."
        
        if go build -o bin/validity-check validity_check.go &> /dev/null; then
            print_status "PASS" "validity-check binary built successfully"
        else
            print_status "FAIL" "Failed to build validity-check binary"
            return 1
        fi
        
        if go build -o bin/microbenchmark microbenchmark.go &> /dev/null; then
            print_status "PASS" "microbenchmark binary built successfully"
        else
            print_status "FAIL" "Failed to build microbenchmark binary"
            return 1
        fi
        
        if go build -o bin/grafana-dashboard visualisation/grafana.go &> /dev/null; then
            print_status "PASS" "grafana-dashboard binary built successfully"
        else
            print_status "FAIL" "Failed to build grafana-dashboard binary"
            return 1
        fi
    else
        print_status "FAIL" "go.mod file not found"
        return 1
    fi
}

# Test Python visualization script
test_python_script() {
    echo "🐍 Testing Python visualization script..."
    
    if [ -f "visualisation/visualizer.py" ]; then
        print_status "PASS" "visualizer.py exists"
        
        # Test if the script can be imported (syntax check)
        if python3 -c "import sys; sys.path.append('visualisation'); import visualizer" &> /dev/null; then
            print_status "PASS" "visualizer.py syntax is valid"
        else
            print_status "FAIL" "visualizer.py has syntax errors"
            return 1
        fi
        
        # Test help output
        if python3 visualisation/visualizer.py --help &> /dev/null; then
            print_status "PASS" "visualizer.py help works"
        else
            print_status "FAIL" "visualizer.py help failed"
            return 1
        fi
    else
        print_status "FAIL" "visualizer.py not found"
        return 1
    fi
}

# Test Grafana dashboard generation
test_grafana_dashboard() {
    echo "📊 Testing Grafana dashboard generation..."
    
    # Create output directory
    mkdir -p grafana
    
    # Run the dashboard generator
    if ./bin/grafana-dashboard &> /dev/null; then
        print_status "PASS" "Grafana dashboard generated successfully"
        
        if [ -f "grafana/r2-benchmark-dashboard.json" ]; then
            print_status "PASS" "Dashboard JSON file created"
            
            # Check if the JSON is valid
            if python3 -c "import json; json.load(open('grafana/r2-benchmark-dashboard.json'))" &> /dev/null; then
                print_status "PASS" "Dashboard JSON is valid"
            else
                print_status "FAIL" "Dashboard JSON is invalid"
                return 1
            fi
        else
            print_status "FAIL" "Dashboard JSON file not created"
            return 1
        fi
    else
        print_status "FAIL" "Failed to generate Grafana dashboard"
        return 1
    fi
}

# Test binary help output
test_binary_help() {
    echo "🔧 Testing binary help output..."
    
    # Test validity-check help
    if ./bin/validity-check --help &> /dev/null; then
        print_status "PASS" "validity-check help works"
    else
        print_status "FAIL" "validity-check help failed"
        return 1
    fi
    
    # Test microbenchmark help
    if ./bin/microbenchmark --help &> /dev/null; then
        print_status "PASS" "microbenchmark help works"
    else
        print_status "FAIL" "microbenchmark help failed"
        return 1
    fi
}

# Check file structure
check_file_structure() {
    echo "📁 Checking file structure..."
    
    local required_files=(
        "types.go"
        "validity_check.go"
        "microbenchmark.go"
        "go.mod"
        "Makefile"
        "requirements.txt"
        "instances/r2.go"
        "instances/s3.go"
        "instances/ec2.go"
        "storage/parquet.go"
        "storage/prom.go"
        "visualisation/visualizer.py"
        "visualisation/grafana.go"
        "README.md"
        "IMPLEMENTATION.md"
    )
    
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "PASS" "File exists: $file"
        else
            print_status "FAIL" "File missing: $file"
            missing_files+=($file)
        fi
    done
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        print_status "FAIL" "Missing files: ${missing_files[*]}"
        return 1
    fi
}

# Main test execution
main() {
    echo "🚀 Starting R2 Benchmark Implementation Tests"
    echo "=============================================="
    
    local test_results=()
    
    # Run all tests
    check_go && test_results+=("PASS") || test_results+=("FAIL")
    check_python && test_results+=("PASS") || test_results+=("FAIL")
    check_python_packages && test_results+=("PASS") || test_results+=("WARN")
    check_file_structure && test_results+=("PASS") || test_results+=("FAIL")
    test_go_module && test_results+=("PASS") || test_results+=("FAIL")
    test_python_script && test_results+=("PASS") || test_results+=("FAIL")
    test_grafana_dashboard && test_results+=("PASS") || test_results+=("FAIL")
    test_binary_help && test_results+=("PASS") || test_results+=("FAIL")
    
    echo ""
    echo "📋 Test Summary"
    echo "==============="
    
    local pass_count=0
    local fail_count=0
    local warn_count=0
    
    for result in "${test_results[@]}"; do
        case $result in
            "PASS")
                ((pass_count++))
                ;;
            "FAIL")
                ((fail_count++))
                ;;
            "WARN")
                ((warn_count++))
                ;;
        esac
    done
    
    echo "✅ Passed: $pass_count"
    echo "❌ Failed: $fail_count"
    echo "⚠️  Warnings: $warn_count"
    
    if [ $fail_count -eq 0 ]; then
        echo ""
        print_status "PASS" "All critical tests passed! Implementation is ready."
        echo ""
        echo "🎉 Next steps:"
        echo "1. Set up your R2 credentials (see IMPLEMENTATION.md)"
        echo "2. Run: make example-validity-check"
        echo "3. Run: make example-benchmark"
        echo "4. Run: make example-visualization"
    else
        echo ""
        print_status "FAIL" "Some tests failed. Please fix the issues above."
        exit 1
    fi
}

# Run the main function
main "$@" 