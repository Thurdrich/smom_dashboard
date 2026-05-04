import csv
import matplotlib.pyplot as plt

# Function to read the CSV file
def read_data(filename):
    data = []
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(row)
    return data

# Main function
def main():
    # Correct CSV filename
    filename = 'data.csv'
    data = read_data(filename)

    # 1. BA vs Onboard chart
    ba_onboard = {}  # Dictionary to hold BA vs Onboard data
    # Fill ba_onboard with appropriate data
    # ... (data processing)

    plt.figure(figsize=(10, 5))
    plt.bar(ba_onboard.keys(), ba_onboard.values())
    plt.title('BA vs Onboard')
    plt.xlabel('BA')
    plt.ylabel('Onboard')
    plt.savefig('ba_vs_onboard.png')

    # 2. Gap distribution chart
    gap_distribution = []  # List to hold gap distribution data
    # ... (data processing)

    plt.figure(figsize=(10, 5))
    plt.hist(gap_distribution, bins=10)
    plt.title('Gap Distribution')
    plt.xlabel('Gap')
    plt.ylabel('Frequency')
    plt.savefig('gap_distribution.png')

    # 3. Personnel Type breakdown chart
    personnel_types = {}  # Dictionary to hold personnel type breakdown
    # ... (data processing)

    plt.figure(figsize=(10, 5))
    plt.bar(personnel_types.keys(), personnel_types.values())
    plt.title('Personnel Type Breakdown')
    plt.xlabel('Type')
    plt.ylabel('Count')
    plt.savefig('personnel_type_breakdown.png')

    # 4. BSO comparison chart
    bso_comparison = {}  # Dictionary for BSO comparison
    # ... (data processing)

    plt.figure(figsize=(10, 5))
    plt.bar(bso_comparison.keys(), bso_comparison.values())
    plt.title('BSO Comparison')
    plt.xlabel('BSO')
    plt.ylabel('Count')
    plt.savefig('bso_comparison.png')

    # 5. Gap by personnel type analysis chart
    gap_by_personnel_type = {}  # Dictionary for gap by personnel type
    # ... (data processing)

    plt.figure(figsize=(10, 5))
    plt.bar(gap_by_personnel_type.keys(), gap_by_personnel_type.values())
    plt.title('Gap by Personnel Type Analysis')
    plt.xlabel('Type')
    plt.ylabel('Gap')
    plt.savefig('gap_by_personnel_type_analysis.png')

if __name__ == '__main__':
    main()