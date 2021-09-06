try:
  import unzip_requirements
except ImportError:
  pass
import json
import numpy as np
from scipy.optimize import newton

MIN_Q_COUNT = 15
Q_START = 5 # The number of questions before starting optimize more than 1 iter

def get_next_trait_estimate(event, context):
    """Given a list of response pattern, calculate the next trait estimate. 
    Input values will be given to this lambda in the form of an event Object.
    event = {
        responsePattern: [
            {
                questionId: "krmsodkA01k",
                a: 1.0,
                b: -2.0,
                isCorrect: true
            },
            ...
        ],
        previousLatentTraitEstimate: -0.8277102
    }

    Input:
        responsePattern: [Response!]!.  The response pattern, having i responses. 
        previousLatentTraitEstimate: Float!. The previous latent trait Estimate (Theta/Ability Level) for the i-1 responses.
    Returns:
        latentTraitEstimate: The current latent trait estimate
        rawEstimate: The raw estimate before clipping/post-processing
        isClipped: Is trait level estimate clipped
        standardError: The standard error (convergence criteria)
        noIter: The number of iterations
        isConverged: Is theta converged
        isEnd: Should the test end based on convergence criteria
    """
    # Input validation
    if not ('responsePattern' in event  and 'previousLatentTraitEstimate' in event \
        and isinstance(event['responsePattern'], list) and len(event['responsePattern']) > 0 \
        and isinstance(event['previousLatentTraitEstimate'], float) ):
        return {
            "statusCode": 500,
            "body": "Malformed Input. Requires responsePattern as [Response]! and previousLatentTraitEstimate as Float"
        }

    # 1. Read the Input Parameters
    a_list = [x['a'] for x in event['responsePattern']]
    b_list = [x['b'] for x in event['responsePattern']]
    u_list = [x['isCorrect'] for x in event['responsePattern']]
    t = event['previousLatentTraitEstimate']

    a_list = np.array(a_list)
    b_list = np.array(b_list)
    u_list = np.array(u_list)

    q_count = len(event['responsePattern'])

    # 2. Calculate the next latent trait with Newton-Rhapson
    df = get_d_log_likelihood_f(a_list, b_list, u_list)
    ddf = get_dd_log_likelihood_f(a_list, b_list, u_list)
    # Make maxiter max(q_count - 10, 1) to not get into diverging issues in the beginning 
    res = newton(df, t, fprime=ddf, full_output=True, tol=1e-03, maxiter= max(q_count - Q_START, 1), disp=False)
    std_err = np.sqrt(1/np.sum(fisher_information(a_list,b_list,t)))
    t = np.clip(res[0], -4, 4)
    
    # Need to convert bool_ (numpy) to bool Else it cant be serialized!
    # https://stackoverflow.com/questions/58408054/typeerror-object-of-type-bool-is-not-json-serializable
    body = {
        "latentTraitEstimate": t,
        "rawEstimate": res[0],
        "isClipped": bool(t == -4 or t == 4),
        "standardError": std_err,
        "noIter": res[1].iterations,
        "isConverged": res[1].converged,
        "isEnd": bool(q_count >= MIN_Q_COUNT and std_err <= 0.3)
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response

def select_question_from_fisher_information(event, context):
    """Given a list of questions, select one with the maximum Fisher information. If multiple is present, select only one.
    Input values will be given to this lambda in the form of an event Object.
    event = {
        questionList: [
            {
                questionID: "krmsodkA01k",
                a: 1.0,
                b: -2.0,
                c: 0.0
            },
            ...
        ],
        latentTraitEstimate: -0.8277102
    }

    Input:
        questionList: [Question!]!.  The question list to select from.
        latentTraitEstimate: Float!. The current latent trait Estimate (Theta/Ability Level).
    Returns:
        questionID: The question id chosen
        itemIndex: The index of the item chosen
        maxFisherInformation: The maximum fisher information present
    """
    # Input validation
    if not ('questionList' in event  and 'latentTraitEstimate' in event \
        and isinstance(event['questionList'], list) and len(event['questionList']) > 0 \
        and isinstance(event['latentTraitEstimate'], float) ):
        return {
            "statusCode": 500,
            "body": "Malformed Input. Requires questionList as [Question]! and latentTraitEstimate as Float"
        }

    # Use Seed from OS unpredictable entropy https://numpy.org/doc/stable/reference/random/generator.html
    rng = np.random.default_rng()

    # 1. Read the Input Parameters
    q_ids = [x['questionID'] for x in event['questionList']]
    a = [x['a'] for x in event['questionList']]
    b = [x['b'] for x in event['questionList']]
    t = event['latentTraitEstimate']

    a = np.array(a)
    b = np.array(b)

    # 2. Calculate all of the Fisher information in all the items
    items_info = fisher_information(a,b,t)
    # Find the indexes of the items with maximum information (have only 1 axis so [0])
    item_max_info_indexes = np.where(items_info==np.max(items_info))[0]
    # Select a random item from the max indexes
    item_index = rng.choice(item_max_info_indexes)

    body = {
        "message": "Success",
        "questionID": q_ids[item_index],
        "itemIndex": int(item_index),
        "maxFisherInformation": float(np.max(items_info))
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response

def two_pl(a, b, t):
    """2PL Implementation (Vectorized). 
    N Students with K Test Items (Should not be the whole item pool!)
    Inputs: 
        a: Discrimination Parameter. Shape of (K,)
        b: Difficulty Parameter. Shape of (K,)
        t: Ability Level (Theta). Shape of (N,)
    Returns:
        Probability matrix of shape (K, N)
    """
    # If t is a matrix, do broadcasting, if not, just make it scalar
    if hasattr(t, '__len__') and (not isinstance(t, str)):
        tt = np.expand_dims(t, axis=1)
    else:
        tt = t
    return 1/(1 + np.exp(-1.7*a*(tt-b)))

def fisher_information(a, b, t):
    p = np.squeeze(two_pl(a, b, t)) # Returns shape of [K,1] -> [K,]
    return 1.7**2 * np.square(a) * p * (1-p)

def get_d_log_likelihood_f(a, b, u):
    """For a single student with latent trait theta.
    Input:
        a: Discrimination Parameter. Shape of (K,)  Questions
        b: Difficulty Parameter. Shape of (K,) Questions
        u: vector correct u_i=1 correct, u_i=0 wrong. Shape of (K,) Reponses
    Result:
        Function of first derivative of log-likelihood suitable for optimization. with Input 
            theta: Latent trait theta. Shape of [1] ?
    """
    def d_log_likelihood(theta):
        p = np.squeeze(two_pl(a, b, theta)) # Returns shape of [K,1] -> [K,]
        return np.sum(1.7*a*(u-p))
    return d_log_likelihood

def get_dd_log_likelihood_f(a, b, u):
    """For a single student with latent trait theta.
    Input:
        a: Discrimination Parameter. Shape of (K,)  Questions
        b: Difficulty Parameter. Shape of (K,) Questions
        u: vector correct u_i=1 correct, u_i=0 wrong. Shape of (K,) Reponses
    Result:
        Function of second derivative of log-likelihood suitable for optimization. with Input 
            theta: Latent trait theta. Shape of [1] ?
    """
    def dd_log_likelihood(theta):  #This is just fisher_information with a negative sign!
        p = np.squeeze(two_pl(a, b, theta)) # Returns shape of [K,1] -> [K,]
        return - np.sum(1.7**2 * np.square(a) * p * (1-p))
    return dd_log_likelihood