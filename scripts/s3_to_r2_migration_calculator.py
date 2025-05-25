import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from typing import Tuple, List
import seaborn as sns

class S3ToR2MigrationCalculator:
    def __init__(self):
        # S3 Egress pricing tiers (per GB)
        self.s3_egress_tiers = [
            (0, 10 * 1024, 0.09),  # 0-10 TB
            (10 * 1024, 50 * 1024, 0.085),  # 10-50 TB
            (50 * 1024, 150 * 1024, 0.07),  # 50-150 TB
            (150 * 1024, float('inf'), 0.05)  # >150 TB
        ]
        
        # S3 GET operations cost per 1000 requests
        self.s3_get_cost = 0.0004
        
        # R2 PUT operations cost per million requests
        self.r2_put_cost = 4.50
        
        # Set style for all plots
        plt.style.use('seaborn-v0_8')
        sns.set_theme()
        
    def calculate_s3_egress_cost(self, data_size_tb: float) -> float:
        """Calculate S3 egress cost for a given data size in TB."""
        total_cost = 0
        remaining_data = data_size_tb * 1024  # Convert TB to GB
        
        for start_gb, end_gb, rate in self.s3_egress_tiers:
            if remaining_data <= 0:
                break
                
            tier_size = min(remaining_data, end_gb - start_gb)
            if tier_size > 0:
                total_cost += tier_size * rate
                remaining_data -= tier_size
                
        return total_cost
    
    def calculate_s3_get_cost(self, num_objects: int) -> float:
        """Calculate S3 GET operations cost for a given number of objects."""
        return (num_objects / 1000) * self.s3_get_cost
    
    def calculate_r2_put_cost(self, num_objects: int) -> float:
        """Calculate R2 PUT operations cost for a given number of objects."""
        return (num_objects / 1_000_000) * self.r2_put_cost
    
    def generate_egress_cost_data(self, max_tb: float = 2000) -> Tuple[List[float], List[float]]:
        """Generate data points for egress cost visualization."""
        data_sizes = np.linspace(0, max_tb, 100)
        costs = [self.calculate_s3_egress_cost(size) for size in data_sizes]
        return data_sizes, costs
    
    def generate_get_cost_data(self, max_objects: int = 1_000_000) -> Tuple[List[int], List[float]]:
        """Generate data points for GET operations cost visualization."""
        num_objects = np.linspace(0, max_objects, 100, dtype=int)
        costs = [self.calculate_s3_get_cost(n) for n in num_objects]
        return num_objects, costs
    
    def generate_put_cost_data(self, max_objects: int = 1_000_000) -> Tuple[List[int], List[float]]:
        """Generate data points for PUT operations cost visualization."""
        num_objects = np.linspace(0, max_objects, 100, dtype=int)
        costs = [self.calculate_r2_put_cost(n) for n in num_objects]
        return num_objects, costs
    
    def plot_egress_cost(self):
        """Plot S3 egress cost vs data size."""
        data_sizes, costs = self.generate_egress_cost_data()
        
        plt.figure(figsize=(12, 6))
        plt.plot(data_sizes, costs, 'b-', linewidth=2)
        plt.xlabel('Data Size (TB/month)', fontsize=12)
        plt.ylabel('Total Cost ($)', fontsize=12)
        plt.title('S3 Egress Cost Analysis', fontsize=14, pad=20)
        plt.grid(True, alpha=0.3)
        plt.savefig('images/s3_egress_cost.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_get_cost(self):
        """Plot S3 GET operations cost vs number of objects."""
        num_objects, costs = self.generate_get_cost_data()
        
        plt.figure(figsize=(12, 6))
        plt.plot(num_objects, costs, 'r-', linewidth=2)
        plt.xlabel('Number of Objects', fontsize=12)
        plt.ylabel('Total Cost ($)', fontsize=12)
        plt.title('S3 GET Operations Cost Analysis', fontsize=14, pad=20)
        plt.grid(True, alpha=0.3)
        plt.savefig('images/s3_get_cost.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_put_cost(self):
        """Plot R2 PUT operations cost vs number of objects."""
        num_objects, costs = self.generate_put_cost_data()
        
        plt.figure(figsize=(12, 6))
        plt.plot(num_objects, costs, 'g-', linewidth=2)
        plt.xlabel('Number of Objects', fontsize=12)
        plt.ylabel('Total Cost ($)', fontsize=12)
        plt.title('R2 PUT Operations Cost Analysis', fontsize=14, pad=20)
        plt.grid(True, alpha=0.3)
        plt.savefig('images/r2_put_cost.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_cost_breakdown(self, data_size_tb: float, num_objects: int):
        """Plot cost breakdown for a specific scenario."""
        costs = {
            'S3 Egress': self.calculate_s3_egress_cost(data_size_tb),
            'S3 GET': self.calculate_s3_get_cost(num_objects),
            'R2 PUT': self.calculate_r2_put_cost(num_objects)
        }
        
        # Calculate percentages for labels
        total = sum(costs.values())
        labels = [f'{k}\n({v/total*100:.1f}%)' for k, v in costs.items()]
        
        plt.figure(figsize=(10, 8))
        plt.pie(costs.values(), labels=labels, autopct='$%.2f',
                colors=sns.color_palette("husl", len(costs)),
                textprops={'fontsize': 12})
        plt.title(f'Cost Breakdown\nData Size: {data_size_tb}TB, Objects: {num_objects:,}', 
                 fontsize=14, pad=20)
        plt.savefig(f'images/cost_breakdown_{data_size_tb}TB.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_comparative_analysis(self):
        """Plot comparative analysis of costs across different scenarios."""
        scenarios = [
            {'name': 'Small', 'data_size_tb': 5, 'num_objects': 100_000},
            {'name': 'Medium', 'data_size_tb': 50, 'num_objects': 1_000_000},
            {'name': 'Large', 'data_size_tb': 200, 'num_objects': 10_000_000},
            {'name': 'Hyperscale', 'data_size_tb': 1000, 'num_objects': 50_000_000},
            {'name': 'Enterprise', 'data_size_tb': 2000, 'num_objects': 100_000_000}
        ]
        
        costs = []
        for scenario in scenarios:
            costs.append({
                'Scenario': scenario['name'],
                'S3 Egress': self.calculate_s3_egress_cost(scenario['data_size_tb']),
                'S3 GET': self.calculate_s3_get_cost(scenario['num_objects']),
                'R2 PUT': self.calculate_r2_put_cost(scenario['num_objects'])
            })
        
        df = pd.DataFrame(costs)
        df.set_index('Scenario', inplace=True)
        
        plt.figure(figsize=(12, 6))
        df.plot(kind='bar', stacked=True)
        plt.title('Cost Comparison Across Scenarios', fontsize=14, pad=20)
        plt.xlabel('Scenario', fontsize=12)
        plt.ylabel('Cost ($)', fontsize=12)
        plt.legend(title='Cost Component')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=0)
        plt.tight_layout()
        plt.savefig('images/cost_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def calculate_total_migration_cost(self, data_size_tb: float, num_objects: int) -> dict:
        """Calculate total migration cost for given data size and number of objects."""
        return {
            's3_egress_cost': self.calculate_s3_egress_cost(data_size_tb),
            's3_get_cost': self.calculate_s3_get_cost(num_objects),
            'r2_put_cost': self.calculate_r2_put_cost(num_objects),
            'total_cost': (
                self.calculate_s3_egress_cost(data_size_tb) +
                self.calculate_s3_get_cost(num_objects) +
                self.calculate_r2_put_cost(num_objects)
            )
        }

def main():
    # Create images directory if it doesn't exist
    import os
    os.makedirs('images', exist_ok=True)
    
    calculator = S3ToR2MigrationCalculator()
    
    # Generate and save plots
    calculator.plot_egress_cost()
    calculator.plot_get_cost()
    calculator.plot_put_cost()
    
    # Generate cost breakdown for each scenario
    scenarios = [
        {'name': 'Small', 'data_size_tb': 5, 'num_objects': 100_000},
        {'name': 'Medium', 'data_size_tb': 50, 'num_objects': 1_000_000},
        {'name': 'Large', 'data_size_tb': 200, 'num_objects': 10_000_000},
        {'name': 'Hyperscale', 'data_size_tb': 1000, 'num_objects': 50_000_000},
        {'name': 'Enterprise', 'data_size_tb': 2000, 'num_objects': 100_000_000}
    ]
    
    for scenario in scenarios:
        calculator.plot_cost_breakdown(scenario['data_size_tb'], scenario['num_objects'])
    
    # Generate comparative analysis
    calculator.plot_comparative_analysis()
    
    # Print cost analysis table
    print("\nMigration Cost Analysis for Different Scenarios:")
    print("-" * 100)
    print(f"{'Scenario':<10} {'Data Size (TB)':<15} {'Objects':<15} {'Total Cost ($)':<15} {'Cost/TB ($)':<15}")
    print("-" * 100)
    
    for scenario in scenarios:
        costs = calculator.calculate_total_migration_cost(
            scenario['data_size_tb'],
            scenario['num_objects']
        )
        cost_per_tb = costs['total_cost'] / scenario['data_size_tb']
        print(f"{scenario['name']:<10} {scenario['data_size_tb']:<15.1f} "
              f"{scenario['num_objects']:<15,d} {costs['total_cost']:<15.2f} {cost_per_tb:<15.2f}")

if __name__ == "__main__":
    main() 