"""LLM prompts for content detection.

Today these target advertisements; to detect and cut something else,
this is the file to edit.
"""

ad_checker_assistant_instructions = """
Your role is to analyze text or files for advertisements. Prioritize accuracy and ensure all responses are concise and well-structured.
When provided with specific scoring or timestamping instructions, follow them carefully.
"""

sponsor_instructions = """Please review the following podcast
description and extract only the names of sponsors, advertisers,
companies, or organizations mentioned. Exclude any other details, links, or additional context.
Provide just the names.

Example Output:
Sponsors: [Company A, Company B]"""


def get_ad_checker_instructions(sponsors=None):
    """
    Generate ad checker instructions with an optional sponsors section.
    """
    # Handle sponsors dynamically
    if sponsors and not (len(sponsors) == 1 and sponsors[0] == ""):
        sponsors_list = ", ".join(sponsors)
        optional_sponsors_section = (
            f"If one or more of these sponsor names are present, increase the confidence "
            + f"score that an ad is present greatly: {sponsors_list}"
        )
    else:
        optional_sponsors_section = ""

    ad_checker_thread_instructions = f"""
        On a scale of 1-100, evaluate the confidence that the attached text contains an advertisement or institutional promotion.

        ### Guidelines for Detection:

        #### Handling Fragmented Content:
        - Evaluate individual text segments. For segments that appear incomplete or ambiguous, include the preceding and following segments within a **10-20 second window** to ensure the full ad is captured.
        - Prioritize removing content if:
          - It contains explicit ad indicators, such as mentions of sponsors, products, or services.
          - It includes calls to action, promotional language, or website/promo code references.
        - It is acceptable to capture some non-adjacent content as long as it ensures the entire ad is removed.
        - Avoid including unrelated segments that clearly lack ad indicators or disrupt the flow of detection.
        - Use the larger window only for content likely to span multiple segments (e.g., longer ad reads or storytelling formats).

        #### General Indicators:
        - Mentions of organizations, sponsors, or products, explicitly or indirectly.
        - Promotion of a service, product, subscription, or institution.
        - Highlighting unique benefits, features, or incentives, such as cost savings or exclusivity.
        - Encouraging listeners to trust or engage with a brand.
        - Contextual framing: Introducing a problem or need before recommending a solution.

        #### Institutional Promotions:
        - Promotion of an organization's **reputation, values, or societal contributions** rather than a specific product or service.
        - Examples include:
          - A corporation highlighting its environmental efforts (e.g., "BP is committed to sustainability and a greener future").
          - A university promoting its brand or academic excellence (e.g., "Georgia Tech is a leader in innovation and research").
          - Government agencies, NGOs, or advocacy groups promoting awareness or community engagement (e.g., "Support our mission to fight climate change").
        - Indicators of institutional promotions:
          - Statements reinforcing credibility, leadership, or legacy (e.g., "A trusted name for over 100 years").
          - Public relations-driven messaging emphasizing goodwill or societal impact.
          - Invitations to explore the organization's work rather than purchase a product (e.g., "Learn more about our mission").

        ##### Gambling and Betting:
        - Mentions of betting platforms, casinos, or wagering apps.
        - Use of odds, disclaimers, or age restrictions (e.g., "Must be 21 or older").
        - Phrases like "risk-free bets," "lock in your picks," or "bet responsibly."

        ##### Tobacco, Nicotine, and Vaping:
        - Mentions of e-cigarettes, vaping pods, nicotine pouches, or smokeless products.
        - Framing products as harm reduction or "cleaner alternatives."
        - Phrases like "quit smoking the smart way," "nicotine without the smoke."

        ##### Pharmaceuticals and Health Claims:
        - Promotion of prescription or over-the-counter drugs, supplements, or treatments.
        - Health claims (e.g., "boost immunity," "clinically proven," "doctor recommended").
        - References to FDA approval or regulatory compliance.

        ##### Adult Content and Intimate Wellness Products:
        - Promotion of dating platforms, adult content, or intimacy-related services.
        - **For men**:
        - Phrases like "natural male enhancement," "improve performance," "testosterone boosters."
        - **For women**:
        - Terms like "intimate wellness," "boost libido," "feminine rejuvenation," "feel sexier."
        - Euphemistic or pseudo-medical language around intimacy, confidence, or bedroom health.
        - Includes supplements, devices, oils, and therapies marketed for sexual benefit or appeal.

        ##### Gender-Targeted Lifestyle and Beauty Promotions:
        - Skincare, makeup, cosmetics, or beauty product promotions.
        - Phrases like "glowing skin," "age-defying," "get your best look."
        - Hair care, waxing, nail, or personal grooming products.
        - Phrases like "salon-quality at home," "confidence starts with your hair."
        - Self-care and empowerment framing.
        - "You deserve it," "treat yourself," "upgrade your routine."
        - Weight loss or body image-focused products (e.g., slimming teas, detox kits, body sculpting).
        - "Flatten your stomach," "get your summer body," "shed stubborn weight."

        #### Common Podcast Ad Categories
        Flag content that includes brand mentions, promo codes, or clear calls to action in these frequent podcast-ad verticals:
        - **Finance & Investing** - credit cards, trading apps, robo-advisors ("get $10 in free BTC").
        - **Tech & Cybersecurity** - VPNs, password managers, cloud backup ("try it free for 30 days").
        - **Food & Beverage Delivery** - meal kits, snack boxes, coffee/wine clubs ("use code PODCAST").
        - **Health & Wellness Services** - telehealth, therapy platforms, fitness apps, at-home lab tests.
        - **DTC Home & Lifestyle** - mattresses, bedding, furniture-in-a-box, home security.
        - **Beauty & Grooming** - razor clubs, hair-loss treatments, skincare subscriptions.
        - **Education & Career** - online courses, coding bootcamps, certificate programs.
        - **Pet Products** - pet-food subscriptions, tele-vet services, training apps.
        - **Entertainment & Media** - audiobooks, streaming services, ticket platforms.
        - **Travel & Mobility** - airlines, vacation bundles, rental cars, micro-mobility.
        - **Charitable & Political Appeals** - nonprofit fundraising, ballot-initiative promotions.

        Look for discount language, free trials, urgency ("sign up today"), or problem-solution framing to confirm promotional intent.

        #### Calls to Action:
        - Language prompting actions like:
          - Visiting a website or using a promo code (e.g., "Use code PODCAST for 20% off").
          - Signing up, downloading, subscribing, or purchasing.
          - Exploring or engaging with a mission, values, or achievements (e.g., "Explore our impact.").

        #### Distinctive Features:
        - Polished delivery styles (e.g., rehearsed tone, slogans, or taglines).
        - Emphasis on specific benefits or features.
        - Changes in tone, speed, or phrasing signaling promotional content.
        - Problem-solution narratives leading to product recommendations.

        #### Common Promotional Elements:
        - Mentions of discounts, limited-time offers, or urgency (e.g., "Save now," "Exclusive to listeners").
        - Encouragement to act immediately (e.g., "Don't wait, act now").
        - References to solving a problem or enhancing a listener's experience.

        {optional_sponsors_section}

        ### Scoring and Timestamping:
        - Assign confidence scores as follows:
          - Above 60: Strong ad indicators (e.g., sponsor mentions, calls to action, promo codes).
          - 40-60: Content in the 40-60 range may include partial ad-like phrases but lacks a clear call to action or sponsorship mention.
          - Below 40: No clear ad indicators.
        - Ads often run for 30-60 seconds, but timestamps should match detected promotional content rather than assume a set length.
        - If multiple ad or promotional segments are detected, provide timestamps for each segment individually. However, if an ad is fragmented across a longer conversational segment, merge timestamps where necessary to capture the full promotional message without splitting it unnaturally.
        - For conversational-style ads that blend with organic content, focus on identifying the entire promotional context rather than isolating individual phrases. Ensure that subtle sponsorship mentions or integrated endorsements are fully captured.

        Output:
        Be concise, providing only the confidence score and the timestamps for each detected ad or promotional segment.

        Return only a valid JSON object with no additional text, explanations, or formatting. The response must strictly follow this format:
        {{
          "confidence_score": 85,
          "timestamps": [
            {{"start": 0.00, "end": 30.00}},
            {{"start": 45.00, "end": 75.00}},
            {{"start": 120.00, "end": 150.00}}
          ]
        }}
    """

    return ad_checker_thread_instructions
