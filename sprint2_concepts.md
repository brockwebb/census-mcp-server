# Sprint 2 Concepts - Design Decisions & Strategic Direction

*Documentation of key insights and strategic decisions that drive our "Census in Your Pocket" implementation*

## 🎯 Core Vision

**"Statistical Intelligence for Normal People"**
- We're not just mapping variables - we're encoding statistical literacy
- Transform "how much do teachers make?" into proper statistical analysis with median (not mean) and confidence intervals
- Make Census data accessible to non-statisticians while keeping it statistically sound
- The real product is intelligence, not just data access

## ⚡ Performance Philosophy

### 300ms Speed KPI
- **Inspired by**: Google's 300ms optimal results research
- **Reality Check**: AI tools take longer, but speed is still critical
- **User Experience**: "Feels fast" is the real metric, not absolute milliseconds
- **Implementation**: Speed as a KPI even if we're not formally measuring it
- **Failure Mode**: If people say it feels too slow, it's bad

### Performance Targets
- **80% of queries**: <100ms (static semantic match)
- **20% of queries**: 300-500ms (dynamic tidycensus search)
- **Unacceptable**: >1000ms for any query

## 📊 The Power Law Strategy (4-64 Rule)

### Mathematical Foundation
- **20% of variables handle 80% of cases** (standard Pareto)
- **4% of variables handle 64% of cases** (power law squared)
- **1% of variables handle ~40% of cases** (the golden core)

### Implementation Strategy
- **Identify the 4%**: ~15-20 variables that handle most queries
- **Static mapping**: These never change (population, income, poverty fundamentals)
- **Maintenance burden**: Minimal - these are Census constants
- **Speed benefit**: Massive for majority of queries

### The Golden Variables
Population, median income, poverty rate, unemployment, median home value, median rent, median age, education levels, major occupation salaries (teacher, nurse, police, engineer, doctor)

## 🧠 Semantic Mapping Strategy

### The Real User Language Problem
People ask **concepts**, not **statistical measures**:
- "How much do teachers make?" (not "median teacher salary")
- "What do houses cost?" (not "median home value")
- "Is it expensive?" (not "cost of living index")
- "How many people?" (not "total population")

### Expanded Semantic Surface Area
Instead of exact matches, support natural language variations:
- **Teacher**: teacher, teaching, educator, elementary teacher, school teacher
- **Income**: income, salary, pay, earnings, wages, make, earn
- **Housing**: cost, price, expensive, home value, house price, property value
- **Population**: people, residents, live, total population, pop

### Sweet Spot Target
- **50-100 semantic mappings** total
- **Core demographics**: 15 concepts × 3-4 natural variations = 45-60 mappings
- **Top occupations**: 10 jobs × 3-4 natural variations = 30-40 mappings
- **Maintenance**: Curated list of core concepts with natural variations

## 🔄 Hybrid Approach Architecture

### Static + Dynamic Strategy
1. **Static check first**: Power law variables for speed
2. **Dynamic fallback**: tidycensus search for comprehensive coverage
3. **Caching**: Successful dynamic searches become static for future
4. **Best of both worlds**: Speed + comprehensiveness

### Census Data Integration Philosophy
- **Don't reinvent Census API calls**: Use tidycensus for data retrieval (R expertise)
- **DO build our own semantic layer**: tidycensus wasn't built for AI/natural language
- **Annual refresh strategy**: Census data changes yearly, perfect for batch processing
- **AI-optimized architecture**: Pre-built search indexes, not real-time R calls
- **Performance-first**: Local semantic lookup vs API calls for variable discovery

### Why Not Pure tidycensus Approach
- **Built for different use case**: Statisticians who know codes vs AI natural language
- **Performance mismatch**: R session waits vs 300ms AI tool targets  
- **Wrong caching strategy**: Per-session cache vs persistent AI-optimized search index
- **Missing semantic layer**: "B19013_001" vs "how much do people make?"

## 🧮 Statistical Best Practices Intelligence

### Auto-Select Right Measures
- **Salary/Income**: Always median (not mean - skewed by high earners)
- **Home values**: Median (not mean - outliers distort)
- **Age**: Median (better central tendency)
- **Population**: Total/sum (makes conceptual sense)
- **Rates**: Percentages with proper denominators

### Response Intelligence
- **Explain the choice**: "Median teacher salary (half earn more, half earn less)"
- **Include uncertainty**: Margin of error with interpretation
- **Statistical education**: Brief context on why median > mean for salaries
- **Data quality flags**: Reliability indicators (good/fair/unreliable)

## 🎭 Tool Selection Psychology

### The Real MCP Problem
Claude sees:
- **Census tools**: Specialized, unfamiliar, requires learning
- **Web search**: Universal, familiar, always works, no cognitive load
- **Choice**: Path of least resistance (web search wins)

### Our Solution Strategy
- **Make tools more attractive**: Emphasize superiority over web search
- **Clear value proposition**: "Official data with margins of error vs unreliable web estimates"
- **Scope clarity**: Explicit about what we DO and DON'T handle
- **Authority positioning**: "AUTHORITATIVE" and "OFFICIAL" in descriptions

## 📈 Query Complexity Classification

### Simple Queries (Static Mapping)
- Direct demographic questions
- Major occupation salaries
- Basic location comparisons
- Core housing/income questions

### Complex Queries (Dynamic Search)
- Unusual occupations
- Specialized variables
- Industry-specific breakdowns
- Advanced geographic combinations

### Out of Scope (Clear Boundaries)
- Non-Census data (teacher salaries are NOT in standard ACS)
- Real-time data
- Private sector surveys
- International comparisons

## 🚀 Success Metrics

### Technical KPIs
- **Response time distribution**: 80% under 100ms, 95% under 500ms
- **Static hit rate**: Percentage of queries using fast static mappings
- **Dynamic search accuracy**: Success rate of tidycensus variable discovery
- **Cache efficiency**: How often dynamic searches become static

### User Experience KPIs
- **Query success rate**: Percentage returning useful data
- **Statistical appropriateness**: Using right measures (median vs mean)
- **Explanation quality**: Users understand results and limitations
- **Scope clarity**: Users understand what Census can/cannot answer

## 🏗️ Architecture Implications

### AI-Optimized Census Pipeline
- **Annual semantic index build**: Fetch ALL Census variables, build search-optimized structures
- **Local semantic lookups**: Pre-computed mappings for 300ms target performance  
- **tidycensus for data retrieval**: Let R handle the actual Census API calls
- **Persistent search index**: SQLite/JSON structures optimized for natural language queries

### Hybrid Variable Engine
- **Semantic index first**: Fast local lookup of concept → variable mappings
- **tidycensus execution**: R handles the actual data retrieval with proper MOE handling
- **Statistical intelligence**: Auto-select proper measures (median vs mean)
- **Performance tiers**: Core concepts <100ms, comprehensive coverage <500ms

### Annual Refresh Process
- **Build semantic index** from complete Census variable catalog (~28k variables)
- **Filter to useful subset** (~2k variables that people actually ask about)
- **Generate natural language aliases** for each variable/concept
- **Create optimized search structures** (JSON + SQLite full-text search)
- **Version and deploy** as part of normal update cycle

## 💎 Where the Gold is Buried

1. **Semantic concept mapping** - Understanding "how much do teachers make" as a statistical question
2. **Power law optimization** - 4% of variables handle 64% of queries  
3. **Statistical intelligence** - Auto-selecting median over mean for income questions
4. **Hybrid performance** - Fast static + comprehensive dynamic
5. **User psychology** - Making Census tools more attractive than web search
6. **Educational value** - Teaching statistical literacy through responses

---

*"We're not building a Census API wrapper - we're building statistical intelligence for normal people."*