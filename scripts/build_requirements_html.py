#!/usr/bin/env python3
"""Generate Requirements Inventory HTML for index.html."""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def bullets_to_html(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    parts: list[str] = []
    buf: list[str] = []
    ul_open = False

    def close_ul():
        nonlocal ul_open
        if ul_open:
            parts.append("</ul>")
            ul_open = False

    def flush_para():
        nonlocal buf
        if buf:
            parts.append("<p>" + html.escape("\n".join(buf)) + "</p>")
            buf = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("•") or (stripped.startswith("-") and len(stripped) > 1):
            flush_para()
            if not ul_open:
                parts.append('<ul class="req-bullets">')
                ul_open = True
            item = stripped.lstrip("•").lstrip("-").strip()
            parts.append("<li>" + html.escape(item) + "</li>")
        elif stripped:
            close_ul()
            buf.append(stripped)
        else:
            flush_para()
            close_ul()
    flush_para()
    close_ul()
    return "".join(parts)


def req_cell(rid, cat, title, body):
    return (
        f'<tr><td class="req-id">{html.escape(rid)}</td>'
        f'<td class="req-cat">{html.escape(cat)}</td>'
        f'<td class="req-cell"><span class="req-title">{html.escape(title)}</span>'
        f"{bullets_to_html(body)}</td></tr>"
    )


def fs_req_row(rid, cat, title, body, example, kpi):
    return (
        f'<tr><td class="req-id">{html.escape(rid)}</td>'
        f'<td class="req-cat">{html.escape(cat)}</td>'
        f'<td class="req-cell"><span class="req-title">{html.escape(title)}</span>'
        f"{bullets_to_html(body)}</td>"
        f'<td class="req-cell">{bullets_to_html(example)}</td>'
        f'<td class="req-kpi">{html.escape(kpi)}</td></tr>'
    )


def bu_ex_req_row(rid, cat, title, body, example):
    return (
        f'<tr><td class="req-id">{html.escape(rid)}</td>'
        f'<td class="req-cat">{html.escape(cat)}</td>'
        f'<td class="req-cell"><span class="req-title">{html.escape(title)}</span>'
        f"{bullets_to_html(body)}</td>"
        f'<td class="req-cell">{bullets_to_html(example)}</td></tr>'
    )


GENERAL_REQS = [
    ("G-FP-1", "Forecasting and Planning", "Future Quota Forecasting Based on Expected Work Volumes",
     "The system shall implement a forecasting capability to predict future quota requirements based on anticipated work volumes. This feature aims to ensure adequate allocation of technicians in each region for upcoming days, aligning workforce availability with projected service demands.\n•\tImplement an algorithm to calculate the necessary quota of technicians required to meet the forecasted work volumes, ensuring sufficient coverage in each region.\n•\tThe platform must accommodate scenarios where unexpected fluctuations in work volumes occur, providing alerts and recommendations for quota adjustments."),
    ("G-FP-2", "Forecasting and Planning", "Automated Technician Allocation Based on Work Forecasts",
     "The system shall implement an automated allocation system to assign technicians to work in specific areas and on specific days based on forecasted work volumes. This feature aims to optimize workforce distribution, ensuring that technician availability aligns with projected service demands in each region\n•\tThe system must analyze factors such as anticipated job types, historical completion rates, and regional demand patterns to inform allocation decisions.\n•\tEstablish protocols for overriding automatic assignments in specific scenarios, allowing manual adjustments by planners."),
    ("G-FP-3", "Forecasting and Planning", "Dynamic Quota Forecast and Technician Allocation Updates",
     "The system shall implement a system to automatically update quota forecasts and technician allocations in real time based on ongoing events. This feature aims to enhance responsiveness and ensure optimal resource distribution by reflecting current conditions and operational changes.\n•\tThe platform shall continuously monitor ongoing events, such as job completions, cancellations, unexpected demand spikes and technician callouts to adjust quota forecasts dynamically\n•\tThe platform must accommodate scenarios where multiple events impact forecast accuracy, providing rapid adjustments to ensure operational continuity."),
    ("G-FP-4", "Forecasting and Planning", "Real-Time Dashboards, Alerts, and Analytics for KPI Monitoring",
     "The system shall be equipped with dashboards, alert mechanisms, and analytics capabilities specifically designed for real-time monitoring and management of quotas. This feature aims to optimize resource allocation by providing key insights into quota utilization, availability, and forecasting, enabling proactive adjustments to meet service demands.\n•\tThe system shall provide customizable dashboards that display real-time metrics related to quota management, including technician availability, allocated versus utilized quotas, and upcoming quota requirements.\n•\tThe system should track, report and visualize routing engine operational data such as unable to route due to capacity, blocking work or lack of availability\n•\tImplement an alert system that automatically notifies quota managers of significant deviations from quota utilization targets or potential shortages.\n•\tThe system shall offer analytics tools to identify trends and forecast future quota needs based on historical data, seasonal patterns, and anticipated service demands.\n•\tLeadership should be able to see the location of the trucks, job details, job status, time on job, time off job and other key factors on a map"),
    ("G-FP-5", "Forecasting and Planning", "Configurable Work Area Segregation by Business Area",
     "The system shall implement configurable work areas to allow for the segregation of regions based on specific business activities such as Maintenance, Construction, and Field Service. This capability ensures that each business area can operate independently within the same geographical location, utilizing tailored maps to optimize operations.\n•\tThe platform shall allow administrators to configure and define work areas specific to each business activity, creating distinct maps for Maintenance, Construction, and Field Service.\n•\tThe system should support visual differentiation between work areas to enhance clarity and operational focus.\n•\tThe platform must support scenarios where work areas overlap, providing mechanisms to manage shared resources or collaborative efforts between business areas."),
    ("G-FP-6", "Forecasting and Planning", "Technician Geographical Area Mapping and Assignment",
     "The system shall enable the mapping of technicians to one or more geographical work areas, with the ability to reassign them to different areas as operational needs evolve. This capability ensures flexible resource deployment and alignment with service demands across various regions\n•\tWork areas should be defined using geographic boundaries, such as cities, districts, or custom zones, to ensure precise mapping.\n•\tEnable the assignment of technicians to multiple geographical areas, allowing them to operate across different regions as required by their skill set and availability.\n•\tThe system should support overlapping area assignments, where technicians can serve in more than one area simultaneously.\n•\tIt should be possible to move technicians to different geographical areas as needed"),
    ("G-FP-7", "Forecasting and Planning", "Technician Shift Configuration",
     "The system shall enable the creation of detailed shifts for technicians, specifying productive and non-productive times, including work blocks, breaks, lunch times, and exceptions such as meetings. This capability ensures precise scheduling and effective management of technician activities throughout their shifts.\n•\tEnable the scheduling of productive time blocks within a shift, detailing periods when technicians are expected to perform work-related tasks.\n•\tAllow for the allocation of non-productive times within a shift, specifying mandatory breaks and lunch periods to ensure compliance with labor regulations\n•\tImplement functionality to schedule exceptions within a shift, such as meetings, training sessions, or other non-standard activities."),
    ("G-FP-8", "Forecasting and Planning", "Technician Management Configuration Interface",
     "The system shall be equipped with an interface for technician management, allowing administrators to quickly configure new technicians, adjust profiles, manage shifts, and allocate regions. This feature aims to streamline technician management processes and enhance operational efficiency.\n•\tThe platform shall provide an interface that allows administrators to create and configure new technician profiles, including personal information, skills, certifications, and contact details.\n•\tThe system should allow for easy modifications to shift schedules, supporting dynamic operational needs.\n•\tThe system should allow specific higher-level users the ability easily move techs from any area to another without restrictions.\n•\tThe system should allow for integration with UXID (Charter\u2019s personnel directory and source of information for some of the technician data)"),
    ("G-RO-1", "Routing Optimization", "Optimized Auto-Routing of Work Orders",
     "The system shall implement optimized auto-routing capabilities to automatically assign work orders based on multiple dynamic factors such as job priority, geography, distance, job requirements, technician skills, and shift schedules. This foundational feature aims to enhance routing efficiency and ensure effective resource utilization across operations.\n•\tThe platform shall evaluate and assign work orders based on priority, which may change over time due to operational needs or customer requests.\n•\tImplement an algorithm that dynamically adjusts routing decisions to reflect updated priorities, ensuring timely completion of high-priority jobs.\n•\tThe system must consider both the proximity of jobs to technicians and the geographic distribution of work orders to enhance routing efficiency\n•\tThe system must include measures to ensure technicians adhere to assigned routes and do not exploit routing adjustments by intentionally avoiding job assignments\n•\tThe system must be able to \u201cdrip feed\u201d, only assigning one, two, or however many configured maximum jobs that a technician can be assigned to through his route\n•\tThis optimization should take place with a high-frequency (it is set to every 5 minutes in the current system)"),
    ("G-RO-2", "Routing Optimization", "Integration of Truck and Technician/Construction Coordinator Geolocation Data into WFM",
     "The system shall integrate geolocation data for both trucks and technicians from an external system. This integration aims to enhance real-time tracking and routing efficiency by providing accurate location data to support field operations.\n•\tEnable real-time tracking of trucks and technicians within the WFM platform, providing dispatchers with visibility into current locations and movement patterns.\n•\tThe system should display geolocation data on maps, offering visual representations to assist with decision-making and route optimization.\n•\tThe system should consume both truck mounted and company owned cellphone GPS data"),
    ("G-RO-3", "Routing Optimization", "Configurable Regional Routing Parameters",
     "The system shall enable configuration of routing parameters specific to geographical areas with different levels of granularity (Region, Management Area, Hub), accommodating diverse operational constraints such as maximum driving distance, job priority levels, and resource availability. This feature ensures that the routing engine operates in alignment with regional business strategies and logistical requirements.\n•\tThe platform shall allow administrators to define and configure routing parameters tailored to each region, including constraints like maximum driving distance, allowable travel times, and job prioritization rules.\n•\tThe access to configured parameters should be role-based to prevent unauthorized users to make these changes\nThe platform must manage scenarios where routing constraints vary significantly between regions, providing flexible configuration options to accommodate diverse operational needs."),
    ("G-RO-4", "Routing Optimization", "Multi-Skill and Skill Level Assignment for Technicians",
     "The system shall enable the assignment of multiple skills and skill levels to technicians, allowing for a comprehensive representation of their expertise. This capability ensures that technicians can be accurately matched to a diverse range of work orders, optimizing resource allocation and service delivery.\n•\tThe platform shall allow administrators to assign multiple skills to each technician, reflecting the breadth of their expertise across different operational areas.\n•\tSkills should be selectable from a predefined list, ensuring consistency and ease of assignment.\n•\tEnable updates to skills and skill levels based on training completion, performance assessments, and certifications."),
    ("G-JA-1", "Job Allocation and Scheduling", "Manual Dispatching and Routing Capability",
     "The system shall provide robust manual dispatching and routing capabilities to allow human intervention when auto-dispatching is not feasible or desirable. This feature ensures flexibility in managing work orders and empowers dispatchers to make informed routing decisions based on situational needs.\n•\tThe platform shall offer an intuitive interface for dispatchers to manually assign work orders to technicians.\n•\tThe interface must support drag-and-drop functionality and provide visibility into technician schedules, skills, and availability.\n•\tImplement mechanisms to easily override auto-dispatching settings and manually route work orders when required."),
    ("G-TS-1", "Technician Status", "Real-Time Dashboards, Alerts, and Analytics for KPI Monitoring",
     "The system shall be equipped with real-time dashboards, alerts, and analytics to provide key performance indicators (KPIs) and swiftly identify issues requiring resolution. This capability enables routers to monitor critical datapoints efficiently and focus their efforts on addressing emerging challenges.\n•\tThe platform shall provide customizable dashboards that display real-time KPIs relevant to field service operations, such as job completion rates, technician / construction coordinator availability, and customer satisfaction scores.\n•\tImplement an alert system that automatically notifies routers of significant deviations from expected KPI thresholds, such as delayed job completions or resource shortages\n•\tUsers should be able to generate reports and visualizations that highlight critical insights and inform decision-making processes.\n•\tThe system must communicate all status changes and all other order related activities via an API, Kafka or other appropriate method externally and in real time."),
]

FS_REQS = [
    ("FS-FP-1", "Forecasting and Planning", "Intelligent Job Size Forecasting",
     "The system shall forecast job duration, utilizing historical factors to enhance prediction accuracy. These factors include, but are not limited to:\n•\tJob type: considering, for example, if it is a new install or a trouble call\n•\tPast job durations: using past durations for similar jobs\n•\tSeasonal variations: considering historical seasonality (ex: winter vs summer)\n•\tTechnician performance: utilizing historical data on individual technician performance\n•\tType of household: considering job size differences in households such as single or multi-dwelling units\n•\tLocation-based trends: incorporating historical geographic data to estimate job sizes\n•\tLine of business: analyzing historical data on Residential, SMB and Enterprise",
     "An install is taking place in a rural area where customers typically have a large front yard, and the technician takes longer to connect the tap to the house at this location than metropolitan areas.\n\nA technician who has just come off training takes longer to do a job than a technician who has been doing that for 5 years",
     "OTA, Overrun"),
    ("FS-FP-2", "Forecasting and Planning", "Real-time quota updates based on day-of job",
     "The system shall continuously and automatically update job quotas throughout the day in response to events and varying field performance that evolves throughout the day:\n•\tQuota Reduction: Automatically decrease quotas in response to constraints\n•\tQuota Increase: Adjust quotas upward when there\u2019s opportunity to take additional work",
     "Poor OTA in the beginning of the day (ex: due to tech callouts) causes appointments to start being missed and getting delayed. Quota in the afternoon should be adjusted to avoid booking new appointments that will further degrade the day\n\nJobs are being completed faster than expected, and additional quota can be assigned to take extra work.\n\nA higher-than-expected amount of cancellations took place throughout the day, and additional quota can be taken.",
     "OTA"),
    ("FS-FP-3", "Forecasting and Planning", "Intelligent Forecasting of Work based on Special Situations",
     "The system shall incorporate predictive analytics capabilities to identify and predict patterns such as low work volume, typical traffic congestion times, holiday traffic variations, and allocate quota accordingly:\n•\tThe platform shall analyze historical data to identify patterns and trends in work volume and traffic conditions across different regions.\n•\tIt must predict future scenarios, including low work volume and traffic congestion",
     "In a dense metropolitan area, traffic at 5pm increases in such a way that techs don\u2019t have the same mobility \u2013 and quota should be decreased during this time\n\nHeavy snowfall is forecasted for the next day, and traffic patterns are expected to change due to blocked roads.",
     "OTA"),
    ("FS-FP-4", "Forecasting and Planning", "Customer-commitment SLAs",
     "The system shall have configurations that support customer-commitment SLAs, and forecast quota to maximize adherence to them:\n•\tScheduled Window: all appointments have a given guaranteed window (e.g. 1 hour), meaning that the technician will always arrive within the promised window.\n•\tQuota Availability: there will always be quota available within a short period from the moment the customer calls Charter (e.g. 2 hours for residential customers)",
     "For appointments which have a 10-11 schedule, the technician will need to get to the customer between 10 and 11.\n\nA customer calls in, our earliest available time should be a maximum of 2 hours from the time of that call).",
     "OTA"),
    ("FS-UA-1", "Utilization and Availability Management", "Optimal Break and Lunch Scheduling for Technicians",
     "The system shall implement a break scheduling feature that identifies and suggests optimal times for technicians to take lunch or breaks during their workday, to minimize disruption to available working time while considering the current day\u2019s circumstances.\n•\tBreak Scheduling Algorithm: The platform shall utilize real-time job schedules, technician locations, and workload data to determine and suggest optimal break times",
     "A technician who has a 12-1pm lunch and then a 1-2pm appointment, ends a job at 11.30am. Instead of going to lunch at 11.30, they sits in \u201cAvailable\u201d until 12 (when no job can be assigned to him) and then take their lunch until 1 and only gets to the 1-2 appointment at 1.30",
     "AW"),
    ("FS-UA-2", "Utilization and Availability Management", "Dynamic Routing of Non-Customer Facing Jobs",
     "The system shall implement a dynamic routing system that effectively assigns non-customer facing jobs to technicians when they have availability without any scheduled customer-facing appointments.\n•\tAvailability Detection: The system must promptly detect and flag periods suitable for non-customer facing job assignments\n•\tJob Routing Algorithm: Implement an algorithm that dynamically routes non-customer facing jobs to technicians during their available periods, prioritizing proximity and resource efficiency.",
     "A technician is available from 1-3pm, since there are no customer-facing jobs during that interval. They can get assigned non-customer facing jobs such as drop buries, CLIs, etc)\n\nA technician finishes customer-facing jobs earlier than expected, allowing immediate assignment of a non-customer facing task.",
     "AW"),
    ("FS-UA-3", "Utilization and Availability Management", "Dynamic Micro-Opportunity Allocation during Available Time",
     "The system shall implement a system that dynamically identifies and allocates micro-opportunities to technicians during unavoidable available time. These opportunities may include quick trainings, coaching sessions with supervisors, or assisting nearby technicians with their tasks through \"Tech Assist\" tickets.\n•\tAvailability Detection: the platform shall monitor technician schedules and detect periods of unavoidable available time, such as delays between jobs or unexpected cancellations.",
     "A technician is available from 1-3pm, since there are no jobs during that interval. To avoid unproductive time, they get assigned a \u201cTech Assist\u201d ticket to help a nearby tech who is overrun.\n\nA technician has 45 minutes until their next job \u2013 this is not enough time for them to complete any other job. A micro-opportunity (ex: 20 min training video) is assigned to them.",
     "AW"),
    ("FS-RO-1", "Routing Optimization", "Identification of Optimal Forward Scheduling Opportunities",
     "The system shall implement a feature that intelligently identifies potential opportunities to pull forward future scheduled work into the current day when there is unused quota available and technicians are in a nearby region.\n•\tOpportunity Detection: Implement an algorithm that evaluates the suitability of pulling forward jobs from future schedules based on technician location, workload, skill match, distance to job and date of future job.\n•\tScenario Handling: Establish protocols to ensure identified opportunities do not conflict with critical future appointments.",
     "A technician is available from 1-3pm, since there are no jobs during that interval. There may be some trouble calls nearby booked for later in the day or even day after, where the customers might be interested in getting them addressed earlier",
     "AW"),
    ("FS-RO-2", "Routing Optimization", "Strategy Implementation for Managing Long Job Overruns",
     "The system shall automatically identify long job overruns and propose solutions\n•\tJob Overrun Detection: The system must automatically flag jobs as overruns when they surpass predefined thresholds.\n•\tScenario Handling: The platform must accommodate various types of jobs and tasks, providing tailored strategies to address overruns effectively.",
     "A technician is overrunning on a job and there\u2019s an available technician nearby \u2013 they can go to help and get the work completed faster.",
     "Overrun"),
    ("FS-RO-3", "Routing Optimization", "Real-time Technician Location-Based Routing for Work Orders",
     "The system shall optimize drive time between jobs by integrating a routing feature that considers the technician's current geographic location when assigning new work orders.\n•\tReal-Time Location Integration: continuously tracking and updating the technician's current geographic location using GPS information (integrated from an external system)\n•\tFirst Job of Day: For the first job of the day, assign the first job of the day based on their predicted starting location, as determined by their schedule (ex: home, depot, etc)",
     "Tech drives 20 miles to an appointment which then gets cancelled and gets the next job routed based on their last job\u2019s location (not where they currently are).\n\nTech attends a warehouse meeting between jobs, and gets the next job routed based on their last job\u2019s location (not the warehouse).\n\nOn Tuesday, a \"drive from home\u201d tech will start their work from the depot (which is 20 miles from his home). Currently their first job is routed based on his home address (and not the depot)",
     "OTA"),
    ("FS-RO-4", "Routing Optimization", "Foresight in Routing Decisions Based on Upcoming Appointment Status",
     "The system shall incorporate forecasting capabilities in its routing system to anticipate upcoming appointment statuses\n•\tThe system must prioritize routing decisions that include technicians who are anticipated to be available within a short timeframe, optimizing proximity and efficiency.\n•\tThe platform must accommodate scenarios where multiple technicians are nearing completion of their jobs, identifying the most optimal candidates for new assignments.\n•\tEstablish protocols to ensure that routing decisions align with service level agreements and operational priorities.",
     "A technician just became available and was routed a job 30 miles away. 5 minutes later, a technician only 1 mile from that job finishes a job and becomes available \u2013 it would be more efficient to wait for the closer technician to finish his work and then assign the job to them.",
     "OTA"),
    ("FS-RO-5", "Routing Optimization", "Cross-Work Zone Routing Optimization",
     "The system shall implement a cross-work zone routing feature that allows for efficient job assignments when technicians and jobs are located near the borders of different work zones.\n•\tProximity-Based Routing Logic: The platform shall evaluate the geographic proximity of jobs and technicians near work zone borders, allowing for cross-zone job assignments when beneficial\n•\tEstablish criteria for determining when cross-zone routing is appropriate, such as distance thresholds or travel time savings.\n•\tEstablish criteria for determining when cross-zone routing is appropriate, such as distance thresholds or travel time savings.",
     "A technician is available in work zone A, and they are very close to a job in work zone B, but doesn\u2019t get assigned the job because the work zones are different.",
     "AW, OTA"),
    ("FS-JA-1", "Job Allocation and Scheduling", "Optimized Scheduling for Customer Appointments",
     "The system shall implement smart scheduling capabilities to optimize booking times for customer appointments\n•\tOptimized Customer Appointment Scheduling: The platform shall use predictive analytics to offer customers optimized appointment slots rather than defaulting to the earliest available time.\n•\tAppointment suggestions should consider factors such as technician availability, proximity, and workload balance to enhance operational efficiency.",
     "Two customers in the same remote town call for an Install. It\u2019s preferrable to schedule those consecutively so that one tech can do both jobs, instead of sending two techs to the jobs.",
     "Drive time, OTA"),
    ("FS-JA-2", "Job Allocation and Scheduling", "Optimized Scheduling for Internal Events",
     "The system shall implement smart scheduling capabilities to identify and suggest optimal times for internal events, such as meetings involving multiple technicians\n•\tAnalyze technician schedules, workloads, and geographic data to propose time slots for internal events that minimize impact on ongoing field operations.\n•\tThe system should continuously update scheduling options to reflect changes in field operations and technician availability.",
     "Meetings are often scheduled without much analysis of what would be the least-disrupting time slot for the field, and may cause OTAs, or less-than-ideal routes",
     "OTA"),
    ("FS-JA-3", "Job Allocation and Scheduling", "Manual Scheduling with Automated Skill Matching and Technician Search",
     "The system shall offer an intuitive interface that allows users to filter and search for technicians based on skills and availability, displaying detailed technician profiles to streamline decision-making.\n•\tThe platform shall implement a skill matching algorithm that evaluates technician profiles against work order requirements, automatically suggesting technicians who are \"routable\" to the job.\n•\tThe system should prioritize technicians based on skill match, proximity, and availability, reducing the need for manual checks by routers.\n•\tThe interface should support advanced search options and sorting capabilities to quickly identify suitable candidates for job assignments.",
     "Routers must individually review each technician's profile to assess their skill sets, geographical location, and availability, which is time-consuming and prone to errors.",
     "AW, OTA"),
    ("FS-TS-1", "Technician Status", "Integration with TechMobile for Technician Status Updates",
     "The system shall integrate with the existing TechMobile front-end to receive real-time status updates from technicians, and to push status updates to TechMobile if needed:\n•\tThe system must support various status updates, such as job start, job completion, break times, and availability changes",
     "A technician will status them as \u201cEn Route\u201d to a job, and this status needs to be reflected in WFM.\n\nA technician is unable to status themself, so a user pushes a status update manually through WFM.",
     ""),
]

MAINT_REQS = [
    ("M-JA-1", "Job Allocation and Scheduling", "Bi-directional integration for real-time work order updates",
     "The system shall maintain a bi-directional & real-time, integration with the work order system of record (Lighthouse):\n\u2022\tWork Order Initiation: All maintenance work orders shall be initiated from Lighthouse, and integrated into WFM\n\u2022\tWork Order Priority: Work order priority will be generated and updated in Lighthouse and sent to WFM on a regular basis (i.e., real time via Kafka feed or other applicable method)\n\u2022\tWork Order Status: Lighthouse should be able to update work order status (e.g. cancelling them for example if they are no longer needed), and WFM platform should send real-time updates regarding work order statuses to Lighthouse, as the work order lifecycle progresses",
     "Lighthouse uses telemetry to raise alarms as needed. As an example, Lighthouse can detect an outage and automatically generate a work order for it.\nLighthouse re-evaluates the priority score (WOPR) of a work order every 5 minutes. Upon every re-evaluation, the score is integrated to WFM.\nAs the tech is updating the Work Order status, WFM is sending real time status updates back to Lighthouse."),
    ("M-JA-2", "Job Allocation and Scheduling", "Ability to Pause Jobs",
     "The system shall support work orders being paused due to a different number of possible reasons and have automations in place to handle paused jobs:\n\u2022\tPause Reasons: the system should support \u201cpause\u201d reasons such as Hold for Higher Priority Work, Awaiting Parts, Local Site Access Required, Third Party Vendor Action Required, No Access, Deferred to Maintenance Window, End of Shift\n\u2022\tAutomations: depending on the pause reason, automations should be in place to unassign the work from the technician (either immediately or after some configurable time), automatically set the work order to another status, or route the work to technicians holding a specific title or shift configuration",
     "A technician determines that a node needs to be shut down temporarily to resolve a work order. To minimize impact to existing customers on the node, the technician defers the work order to a nightly crew."),
    ("M-JA-3", "Job Allocation and Scheduling", "Support for Multiple Active Work Orders on a Node",
     "The system shall allow for single node to have multiple active work orders concurrently\n\u2022\tMulti-Work Order: Each node can have multiple active work orders at the same time, and those work orders can be assigned to different technicians",
     "A node for a designated geographical area has several work orders associated with it."),
    ("M-RO-1", "Routing Optimization", "Assigning Urgent Work to Technician",
     "The system shall be capable of assigning urgent tasks to technicians who are currently engaged in ongoing work\n\u2022\tUrgent Task Allocation: The platform shall support the allocation of urgent tasks to technicians who are actively working on existing jobs, allowing for the prioritization of critical work.\n\u2022\tAssignment Logic: The system must evaluate the technician's current work and its priority, as well as proximity to the urgent task location to optimize assignment decisions.\n\u2022\tOverriding Logic: The system should be able to have rules for overriding existing work with higher priority work which should be used to determine if and override is needed and what specific override cases are allowed",
     "A ROC detects that an outage needs to be addressed in node A, so they assign work to a tech who is working on lower priority work."),
    ("M-RO-2", "Routing Optimization", "Re-Assignment of Pended Maintenance Work",
     "The system shall implement logic to keep paused tasks assigned to the same technician and automatically reassign them if a specified threshold of time has passed since the task was paused.\n\u2022\tWork Continuity: The system shall retain paused tasks with the originally assigned technician, maintaining continuity in task management\n\u2022\tTracking Pauses: The platform must track the duration of task pauses, providing visibility into the time elapsed since the task was paused\n\u2022\tReassignment Logic: Implement logic to automatically reassign paused tasks to the next available technician if the pause duration exceeds a predefined threshold (e.g., 2 hours), prioritizing reassignment based on technician availability, skill match, and proximity to the task location",
     "A technician working on a job is notified that a critical outage needs to be addressed. The tech then pauses the current work order and heads to the outage to resolve it. Once complete with the outage work order, the tech resumes work on the work order that had been paused."),
    ("M-FP-1", "Forecasting and Planning", "Supporting Different Shift Types for Regular or On-Call Work",
     "The system shall support different shift types, specifically enabling technicians to be available for on-call duties outside their regular work shifts\n\u2022\tOn-Call Scheduling: The platform must allow for the scheduling of technicians to be on call during specified time slots outside their regular shift hours.\n\u2022\tJob Assignment for On-Call Shifts: The WFM platform should be able to assign jobs to technicians which are \u201cOn call\u201d\n\u2022\tShift-Based Work Area Assignment: Allow administrators to configure and assign different work areas for technicians based on their shift type (regular vs. on-call).",
     "Technicians may have a designated timeframe where they are \u201con-call\u201d \u2013 meaning that they can be called upon to resolve an urgent issue outside of their normal shift hours."),
    ("M-FP-2", "Forecasting and Planning", "Technician team creation",
     "The system shall allow for the creation, modification, and deletion of technician teams.\n\u2022\tEach team should have attributes such as team name, team leader, etc\n\u2022\tEach technician can be assigned to one or more teams\n\u2022\tThe team\u2019s node coverage is determined by the nodes of all the technicians combined\n\u2022\tA visual dashboard should be available for easy configuration of different teams\n\u2022\tTeams should be visually displayed and selectable for routing purposes",
     "An administrator can create a team of technicians within the system. The team has a roster of technicians and a list of attributes such as: team name, team leader, etc. A dashboard shows a list of teams for the ROC agents."),
    ("M-TS-1", "Technician Status", "Technician Record \u2013 Day of Job dashboard",
     "The system shall present a dashboard of all active techs and present alerts for specific conditions such as length of time on job, length of time off job, significant location change, etc\n\u2022\tDetailed Documentation: A dashboard user may add \u201cnotes\u201d to an alert so other users who see the same alert can read the prior comments and add as needed",
     "A back office agent observes that a technician has been in \u201cin progress\u201d status longer than anticipated. The agent reaches out to the technician to discuss the inconsistencies and then appends a note to the technician / work order record documenting their conversation and with a timestamp."),
]

CONST_REQS = [
    ("C-JA-1", "Job Allocation and Scheduling", "Construction Survey Distribution",
     "The system shall allow for efficiently managing and distributing construction surveys to designated construction coordinators:\n\u2022\tAuto-routing: Route surveys to coordinators based on predefined criteria such as the geographic location of the construction coordinator, project type, survey type (desktop or on-site) or coordinator skills\n\u2022\tMultiple assignments: Allow for the construction coordinators to receive and see multiple surveys (as opposed to taking care of them one by one)",
     "Multiple surveys are created, and each of them is automatically assigned to a construction coordinator that meets the job criteria."),
    ("C-JA-2", "Job Allocation and Scheduling", "Tracking Construction Coordinator Activities",
     "The system shall formally track the activities of construction coordinators, such as regular on-site check-in visits and technical quality assurance (TQA) inspections.\n\u2022\tDifferent work types: Have different work types for these (on-site check-in visits, TQA inspections, etc), and enable these work items to be completed formally in the system, with fields such as assignee, due date, start and end date\n\u2022\tStatus updates: Sync the status of these items back to PRISM",
     "On-site check-in visits and TQA inspections should be tracked in WFM \u2013 nowadays they are all done offline and done up to the discretion of the construction coordinator.\n\nExamples of coordinator tasks include Surveys,\nSite Visits, TQA,\nAdministrative \u2013 Internal, Administrative - External"),
    ("C-JA-3", "Job Allocation and Scheduling", "Automated Scheduling of Construction Coordinator Tasks",
     "The system shall have functionality to automatically create work and assign it to a construction coordinator\n\u2022\tAuto-generated work: Some work (such as on-site check-in visits, TQA inspections, etc) should be automatically created and triggered based on parameters such as \u201cFrequency of check-ins\u201d, or \u201cProject type\u201d\n\u2022\tAuto-assignment: Once work is created, it should automatically be assigned to the construction coordinator assigned to the project (or based on availability, if multiple coordinators can take that task)",
     "Instead of being up to the discretion of the coordinator (as it is today), regular on-site visits and inspections should be scheduled for greater visibility and control over the work being done."),
    ("C-JA-4", "Job Allocation and Scheduling", "Construction Coordinator Project Assignment",
     "The system shall provide automatic assignment capabilities for mapping a construction coordinator to a project\n\u2022\tAssignment criteria: Project assignments to construction coordinators should be done based on different criteria, but mainly ZIP code\n\u2022\tWorkload balancing: Assignment should take into consideration current workload from the coordinator, and coordinators can be mapped to multiple projects at the same time\n\u2022\tManual intervention: Overriding the assignment manually should be possible, and controlled via RBAC (role based access controls) so that only construction supervisors can do this",
     "As soon as a new construction project starts, it can be routed to a construction coordinator that covers the area and is able to lead that project."),
    ("C-JA-5", "Job Allocation and Scheduling", "PRISM to remain as the system of record for work orders",
     "The system shall receive work orders or tasks, always having PRISM as the source of record for construction work orders\n\u2022\tSource in PRISM: Projects are triggered in PRISM, which then will trigger work such as Surveys and Construction work\nThese work items then need to be integrated to WFM for routing and dispatching",
     "A new survey request is created in PRISM, which then gets automatically integrated to WFM for routing and dispatching."),
    ("CA-JA-6", "Job Allocation and Scheduling", "Ability to see availability for walkout scheduling",
     "The system shall enable the user talking to a customer to immediately see available timeslots for scheduling a walkout to the construction site.\n\u2022\tVisualizing Appointment slots: User should be able to visually pick and choose a walkout timeslot from a list of available times\n\u2022\tRouting Walkout: upon selecting the timeslot, the walkout should automatically be routed to the appropriate construction coordinators",
     "A Charter representative is talking to a customer, to agree on a time for a walkout. At present, an immediate agreement cannot be achieved, since the representative can\u2019t yet see the availability of construction coordinators."),
    ("C-FP-1", "Forecasting and Planning", "Mapping Construction Coordinators and Supervisors to ZIP Codes or Work Areas",
     "The system shall enable for construction coordinators to be assigned to one or more ZIP codes or Work Areas\n\u2022\tGeographical assignment: The platform must provide functionality to map construction coordinators and supervisors to designated ZIP codes or Work Areas\n\u2022\tVisualizations: Provide visualization tools, such as maps, to clearly depict coverage areas and personnel assignments",
     "Construction coordinators cover different ZIP codes / work areas, depending on their geographical location."),
    ("C-FP-2", "Forecasting and Planning", "Construction Coordinator Profile Management",
     "The system shall enable the management of construction coordinators.\n\u2022\tProfile configuration: Coordinators can have different profile fields or properties such as work area ownership, skills, shift configurations, contact information, etc\n\u2022\tRouting and dispatching logic: Routing and dispatching logic should consider the coordinators\u2019 profiles (e.g. skills, availability) when assigning different work",
     "A construction coordinator\u2019s profile can be set up in WFM, with the appropriate skills and shift configuration."),
    ("C-TS-1", "Technician Status", "Receive status updates from construction coordinator",
     "The system shall be able to receive status updates from the Construction coordinator in the field\n\u2022\tMultiple statuses: Status might include \u201cBreak\u201d, \u201cOn-site\u201d, etc\n\u2022\tRouting and dispatching logic: Routing should consider statuses to perform new work assignments (for example not assigning work when the tech is on \u201cBreak\u201d)",
     "As the coordinator proceeds with his tasks, they will status themselves in the field work platform \u2013 and the status should flow back to WFM."),
]


def build_coverage_html() -> str:
    intro_wfm = (
        "The specific requirements for the WFM system are outlined in this section \u2013 with each requirement being mapped to a key area as defined below.\n"
        "\u2022\tForecasting & Planning \u2013 predicting workload, job durations, and adjusting quota accordingly\n"
        "\u2022\tUtilization & Availability Management \u2013 managing technician time use, including breaks, idle time, non-customer work, and training\n"
        "\u2022\tRouting & Optimization \u2013 dealing with real-time decisions on technician movement, travel efficiency, and proximity\n"
        "\u2022\tJob Allocation & Scheduling \u2013 ensuring work is matched to the right technician based on skill, timing, and location\n"
        "\u2022\tTechnician Status \u2013 receiving status updates to accurately reflect technician movement in WFM"
    )
    intro_general = (
        "The general requirements are applicable across all business areas (Field Service, Maintenance, and Construction). The WFM system must deliver robust capabilities for routing, quota planning, and technician management, essential for enhancing operational efficiency. It is crucial that the WFM system is highly configurable. Any values mentioned throughout this document (such as Key Performance Indicators (KPIs), customer commitments, or maximum drive time) should be easily adjustable within the WFM system to accommodate the diverse needs of different business areas.\n"
        "The requirements below are crafted towards \u201ctechnicians\u201d, but for Construction it should be assumed they are also applicable to construction coordinators, supervisors and in-house construction crews."
    )
    intro_fs = (
        "The WFM requirements that are specifically tailored to the Field Service area, addressing unique operational needs and enhancing technician management, routing, and service delivery are detailed below."
    )
    intro_maint = (
        "WFM system requirements for the Maintenance area, emphasizing seamless integration with the Lighthouse work order system for real-time updates and management. The system supports job deferral, reassignment, multiple active work orders, and urgent task allocation, while enhancing technician management with features like on-call scheduling, team configuration, and a dashboard for tracking and documenting technician activities."
    )
    intro_const = (
        "The WFM system requirements specific to the Construction area focus on the efficient distribution and management of construction surveys, automated scheduling of tasks, and assignment of coordinators to projects based on geographic and workload criteria. It emphasizes seamless integration with PRISM for work order management, comprehensive profile management, and real-time status updates to optimize routing and dispatching processes."
    )

    general_rows = "\n".join(req_cell(*r) for r in GENERAL_REQS)
    fs_rows = "\n".join(fs_req_row(*r) for r in FS_REQS)
    maint_rows = "\n".join(bu_ex_req_row(*r) for r in MAINT_REQS)
    const_rows = "\n".join(bu_ex_req_row(*r) for r in CONST_REQS)

    return f"""      <div class="section-block"><h3>Coverage by Capability</h3>
        <h4 class="req-h4">WFM Requirements</h4>
        <div class="req-intro">{bullets_to_html(intro_wfm)}</div>
        <h4 class="req-h4">General requirements</h4>
        <div class="req-intro">{bullets_to_html(intro_general)}</div>
        <table class="task-table req-table"><thead><tr><th>ID</th><th>Category</th><th>Requirement</th></tr></thead><tbody>
{general_rows}
        </tbody></table>
        <h4 class="req-h4">Field Service Requirements</h4>
        <div class="req-intro"><p>{html.escape(intro_fs)}</p></div>
        <table class="task-table req-table"><thead><tr><th>ID</th><th>Category</th><th>Requirement</th><th>Example</th><th>KPI affected</th></tr></thead><tbody>
{fs_rows}
        </tbody></table>
        <h4 class="req-h4">Maintenance Requirements</h4>
        <div class="req-intro"><p>{html.escape(intro_maint)}</p></div>
        <table class="task-table req-table"><thead><tr><th>ID</th><th>Category</th><th>Requirement</th><th>Example</th></tr></thead><tbody>
{maint_rows}
        </tbody></table>
        <h4 class="req-h4">Construction Requirements</h4>
        <div class="req-intro"><p>{html.escape(intro_const)}</p></div>
        <table class="task-table req-table"><thead><tr><th>ID</th><th>Category</th><th>Requirement</th><th>Example</th></tr></thead><tbody>
{const_rows}
        </tbody></table>
      </div>"""


def patch_index():
    text = INDEX.read_text()
    coverage = build_coverage_html()

    # Replace Coverage by Capability section
    pattern = r'      <div class="section-block"><h3>Coverage by Capability</h3>[\s\S]*?      </div>\n    </div>`'
    if not re.search(pattern, text):
        raise SystemExit("Coverage section not found")
    text = re.sub(pattern, coverage + "\n    </div>`", text, count=1)

    # Add requirements CSS if missing
    css = """
.req-h4 { font-size: 14px; font-weight: 700; color: var(--text); margin: 20px 0 10px; }
.req-intro { font-size: 12px; line-height: 1.6; color: var(--text); margin-bottom: 14px; }
.req-intro p { margin: 0 0 8px; }
.req-bullets { margin: 8px 0 8px 18px; padding: 0; font-size: 12px; line-height: 1.55; }
.task-table.id-table { table-layout: fixed; }
.task-table.id-table th:first-child,
.task-table.id-table td:first-child,
.req-table th:first-child,
.req-table td.req-id,
.req-table .req-id {
  white-space: nowrap;
  vertical-align: top;
  width: 88px;
  min-width: 88px;
  max-width: 88px;
}
.task-table.id-table td:first-child,
.req-table .req-id { font-weight: 700; }
.req-table .req-cat { white-space: nowrap; vertical-align: top; width: 140px; font-size: 11px; }
.req-table .req-kpi { white-space: nowrap; vertical-align: top; width: 90px; font-size: 11px; }
.req-table .req-cell { vertical-align: top; line-height: 1.55; max-width: 420px; }
.req-table .req-title { font-weight: 700; display: block; margin-bottom: 6px; }
.req-table .req-cell p { margin: 0 0 8px; }
"""
    if ".req-h4" not in text:
        text = text.replace(".task-table tr:hover td { background: #EEF3FA; }", ".task-table tr:hover td { background: #EEF3FA; }\n" + css)

    INDEX.write_text(text)
    print("Patched", INDEX)


if __name__ == "__main__":
    patch_index()
